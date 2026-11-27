"""Enregistrement en base d'une collecte (S1 → S2 → A1) et lecture pour le lot 2.

    resultat = enregistrer_collecte(session, collecte)
    session.commit()   # comme le lot 2, le lot 1 ne fait jamais de commit lui-même

Règles :
- un document déjà reçu à l'identique (mêmes empreintes) est ignoré ;
- un document qui change devient une nouvelle version : « texte_modifie » si son texte
  change, « changement_etat » si seul son état change (sort, date). Dans les deux cas
  l'extraction est refaite sur la nouvelle version : le lot 2 ne lit que des changements,
  c'est donc par eux qu'il apprend qu'un amendement a été adopté ou rejeté ;
- chaque passage laisse une ligne ``execution_collecte`` (statut « ok » ou « ecart »).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from leypilot.collecte.cibles import CIBLES_ARTICLES, CIBLES_SUBDIVISIONS
from leypilot.collecte.comparaison_legi import comparer, confirmer
from leypilot.collecte.schemas import Changement, Passage, changements_du_texte
from leypilot.collecte.sources.base import Collecte, DocumentBrut, Source
from leypilot.collecte.vers_lot2 import (
    TYPES_LOT2,
    changement_detecte,
    document_filtre,
    motif_changement_retenu,
    motif_document_retenu,
)
from leypilot.commun.base import maintenant
from leypilot.commun.llm import ServiceLLM
from leypilot.commun.modeles.collecte import (
    ChangementExtrait,
    Cible,
    Document,
    ExecutionCollecte,
)


@dataclass
class ResultatCollecte:
    execution_id: int
    nouveaux: list[int] = field(default_factory=list)  # documents ajoutés (toutes versions)
    ignores: int = 0  # documents déjà connus à l'identique
    changements: list[int] = field(default_factory=list)
    ecarts: list[str] = field(default_factory=list)  # anomalies vues à l'enregistrement


@dataclass
class LivraisonLot2:
    """Ce qui part vers le lot 2, et ce qui ne part pas, avec la raison (rien en silence)."""

    paires: list[tuple[dict[str, Any], dict[str, Any]]] = field(default_factory=list)
    retenus: list[tuple[int, str]] = field(default_factory=list)  # (changement_id, raison)


def _derniere_version(session: Session, document: DocumentBrut) -> Document | None:
    return session.scalars(
        select(Document)
        .where(Document.source == document.source, Document.identifiant == document.identifiant)
        .order_by(Document.version.desc())
        .limit(1)
    ).first()


def _ligne_changement(changement: Changement, document_id: int) -> ChangementExtrait:
    return ChangementExtrait(
        document_id=document_id,
        operation=changement.operation.value,
        code=changement.code,
        article=changement.article,
        localisation=changement.localisation,
        dispositif=changement.dispositif,
        parametre=changement.parametre,
        objet=changement.objet,
        ancienne_valeur=changement.ancienne_valeur,
        nouvelle_valeur=changement.nouvelle_valeur,
        passage_debut=changement.passage.debut,
        passage_fin=changement.passage.fin,
        passage_texte=changement.passage.texte,
        passage_precedent=(
            changement.passage_precedent.model_dump() if changement.passage_precedent else None
        ),
        clauses_application=list(changement.clauses_application),
        methode=changement.methode,
        coordination=changement.coordination,
        alinea_projet=changement.alinea_projet,
        statut=changement.statut,
        motifs=[m.value for m in changement.motifs],
    )


def enregistrer_collecte(
    session: Session, collecte: Collecte, service: ServiceLLM | None = None
) -> ResultatCollecte:
    """``service`` : couche LLM de P2 pour le secours ; sans lui, les lignes sans formule
    restent « à revoir » pour un humain."""
    execution = ExecutionCollecte(source=collecte.source, fichier=collecte.fichier)
    session.add(execution)
    session.flush()
    resultat = ResultatCollecte(execution_id=execution.id)

    for brut in collecte.documents:
        precedent = _derniere_version(session, brut)
        if precedent and (precedent.empreinte_texte, precedent.empreinte_etat) == (
            brut.empreinte_texte,
            brut.empreinte_etat,
        ):
            resultat.ignores += 1
            continue
        if precedent is None:
            evenement = "nouveau"
        elif precedent.empreinte_texte != brut.empreinte_texte:
            evenement = "texte_modifie"
        else:
            evenement = "changement_etat"
        ligne = Document(
            source=brut.source,
            identifiant=brut.identifiant,
            version=(precedent.version + 1) if precedent else 1,
            version_precedente_id=precedent.id if precedent else None,
            evenement=evenement,
            empreinte_texte=brut.empreinte_texte,
            empreinte_etat=brut.empreinte_etat,
            nature=brut.nature,
            type_texte=brut.type_texte,
            titre=brut.titre,
            date_document=brut.date_document,
            url_officielle=brut.url_officielle,
            nor=brut.nor,
            eli=brut.eli,
            dossier_legislatif=brut.dossier_legislatif,
            numero_amendement=brut.numero_amendement,
            etape=brut.etape,
            etat=_json(brut.etat),
            meta=_json(brut.meta),
            texte=brut.texte,
            chemin_brut=brut.chemin_brut,
            execution_id=execution.id,
        )
        session.add(ligne)
        session.flush()
        resultat.nouveaux.append(ligne.id)
        if brut.date_document is None and brut.type_texte.value in TYPES_LOT2:
            # Jamais écarté en silence : l'administrateur est alerté par l'écart.
            resultat.ecarts.append(
                f"{brut.source} {brut.identifiant} : document sans date, "
                "ses changements ne peuvent pas partir vers le lot 2"
            )
        if brut.source == Source.LEGI:
            changements = _changements_legi(session, ligne, brut, precedent)
        else:
            changements = changements_du_texte(ligne.id, brut.texte, service)
        for changement in changements:
            extrait = _ligne_changement(changement, ligne.id)
            session.add(extrait)
            session.flush()
            resultat.changements.append(extrait.id)

    execution.fin = maintenant()
    execution.nb_lus = collecte.nb_lus
    execution.nb_attendus = collecte.controle.attendus
    execution.nb_recus = collecte.controle.recus
    execution.nb_retenus = len(collecte.documents)
    execution.ecarts = list(collecte.controle.ecarts) + resultat.ecarts
    execution.statut = "ok" if not execution.ecarts else "ecart"
    return resultat


def _changements_legi(
    session: Session, ligne: Document, brut: DocumentBrut, precedent: Document | None
) -> list[Changement]:
    """Comparaison avec la version précédente, puis confirmation par le JO modificateur."""
    code = brut.identifiant.split("/", 1)[0]
    article = str(brut.meta.get("num", ""))
    legi = comparer(
        ligne.id,
        code,
        article,
        precedent.texte if precedent else None,
        brut.texte,
        str(brut.etat.get("etat", "")),
        precedent.id if precedent else None,
    )
    modificateurs = list(brut.meta.get("jorf_modificateurs") or [])
    lignes_jo = session.scalars(
        select(ChangementExtrait)
        .join(Document)
        .where(
            Document.source == Source.JORF,
            Document.identifiant.in_(modificateurs),
            ChangementExtrait.article == article,
        )
    ).all()
    return confirmer(legi, [_schema(jo) for jo in lignes_jo])


def _json(valeurs: dict[str, Any]) -> dict[str, Any]:
    """Dates et autres objets en texte, pour une colonne JSON."""
    return {
        cle: (valeur.isoformat() if hasattr(valeur, "isoformat") else valeur)
        for cle, valeur in valeurs.items()
    }


def charger_cibles(session: Session) -> int:
    """Remplit la table ``cible`` au premier démarrage. Renvoie le nombre de lignes ajoutées."""
    if session.scalars(select(Cible).limit(1)).first() is not None:
        return 0
    lignes = [
        Cible(dispositif=d, code=code, article=article, niveau=cible.niveau, confirme=True)
        for (code, article), cible in CIBLES_ARTICLES.items()
        for d in cible.dispositifs
    ]
    lignes += [
        Cible(
            dispositif=d,
            code="code général des impôts",
            article=article,
            subdivision=motif.pattern,
            niveau="coeur",
            confirme=True,
        )
        for article, motif, d in CIBLES_SUBDIVISIONS
    ]
    session.add_all(lignes)
    return len(lignes)


def _brut(document: Document) -> DocumentBrut:
    return DocumentBrut(
        source=document.source,
        identifiant=document.identifiant,
        nature=document.nature,
        type_texte=document.type_texte,
        titre=document.titre,
        date_document=document.date_document,
        url_officielle=document.url_officielle,
        texte=document.texte,
        nor=document.nor,
        eli=document.eli,
        dossier_legislatif=document.dossier_legislatif,
        numero_amendement=document.numero_amendement,
        etape=document.etape,
    )


def _schema(ligne: ChangementExtrait) -> Changement:
    return Changement(
        document_id=ligne.document_id,
        operation=ligne.operation,
        code=ligne.code,
        article=ligne.article,
        localisation=ligne.localisation,
        dispositif=ligne.dispositif,
        parametre=ligne.parametre,
        objet=ligne.objet,
        ancienne_valeur=ligne.ancienne_valeur,
        nouvelle_valeur=ligne.nouvelle_valeur,
        passage=Passage(
            document_id=ligne.document_id,
            debut=ligne.passage_debut,
            fin=ligne.passage_fin,
            texte=ligne.passage_texte,
        ),
        passage_precedent=(
            Passage.model_validate(ligne.passage_precedent) if ligne.passage_precedent else None
        ),
        methode=ligne.methode,
        coordination=ligne.coordination,
        alinea_projet=ligne.alinea_projet,
        clauses_application=ligne.clauses_application,
        statut=ligne.statut,
        motifs=ligne.motifs,
    )


def pour_lot2(session: Session, apres_changement_id: int = 0) -> LivraisonLot2:
    """Paires (``DocumentFiltre``, ``ChangementDetecte``) à transmettre au lot 2, dans
    l'ordre des identifiants, et changements retenus avec leur raison. Le lot 2 garde le
    dernier identifiant traité."""
    livraison = LivraisonLot2()
    lignes = session.scalars(
        select(ChangementExtrait)
        .where(ChangementExtrait.id > apres_changement_id)
        .order_by(ChangementExtrait.id)
    )
    for ligne in lignes:
        changement, document = _schema(ligne), _brut(ligne.document)
        raison = motif_changement_retenu(changement) or motif_document_retenu(document)
        if raison:
            livraison.retenus.append((ligne.id, raison))
            continue
        filtre = document_filtre(ligne.document.id, document)
        detecte = changement_detecte(ligne.id, changement)
        assert filtre is not None and detecte is not None
        livraison.paires.append((filtre, detecte))
    return livraison
