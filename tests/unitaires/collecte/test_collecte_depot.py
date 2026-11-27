"""Enregistrement en base, versions d'un document et contrat 1 → 2."""

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import select

from leypilot.collecte import depot, vers_lot2
from leypilot.collecte.completude import Rapport
from leypilot.collecte.sources import jorf
from leypilot.collecte.sources.base import Collecte, DocumentBrut, Source, TypeTexte
from leypilot.collecte.textes import normaliser
from leypilot.commun.modeles.collecte import ChangementExtrait, Cible, Document, ExecutionCollecte
from leypilot.mesure.schemas import Changement as ChangementLot2


def _amendement(sort: str | None, texte: str) -> DocumentBrut:
    return DocumentBrut(
        source=Source.AN,
        identifiant="AMANR5L17PO59048B0324P0D1N002211",
        nature="AMENDEMENT",
        type_texte=TypeTexte.AMENDEMENT,
        titre="Amendement n° I-2211",
        date_document=None,
        url_officielle="https://www.assemblee-nationale.fr/",
        texte=normaliser(texte),
        etat={"sort": sort},
        numero_amendement="I-2211",
    )


def _collecte(*documents: DocumentBrut, ecarts: list[str] | None = None) -> Collecte:
    return Collecte(Source.AN, "test", list(documents), Rapport(1, 1, ecarts or []), len(documents))


TEXTE = (
    "I. – À la quatrième phrase du I de l'article 244 quater B du code général des impôts, "
    "le taux : « 30 % est remplacé par le taux : « 20 % »."
)


def test_versions_d_un_document(session):
    premier = depot.enregistrer_collecte(session, _collecte(_amendement(None, TEXTE)))
    assert len(premier.nouveaux) == 1 and len(premier.changements) == 1

    # Même document, même état : ignoré.
    assert depot.enregistrer_collecte(session, _collecte(_amendement(None, TEXTE))).ignores == 1

    # Le sort change : nouvelle version, et ses changements repartent vers le lot 2
    # (c'est ainsi que le lot 2 apprend l'adoption).
    sort = depot.enregistrer_collecte(session, _collecte(_amendement("Adopté", TEXTE)))
    assert len(sort.changements) == 1

    # Le texte change : nouvelle version et nouvelle extraction.
    rectifie = TEXTE.replace("« 20 % »", "« 25 % »")
    modifie = depot.enregistrer_collecte(session, _collecte(_amendement("Adopté", rectifie)))
    assert len(modifie.changements) == 1

    versions = session.scalars(select(Document).order_by(Document.version)).all()
    assert [(v.version, v.evenement) for v in versions] == [
        (1, "nouveau"),
        (2, "changement_etat"),
        (3, "texte_modifie"),
    ]
    assert versions[2].version_precedente_id == versions[1].id


def test_execution_et_ecarts(session):
    date_ = replace(_amendement(None, TEXTE), date_document=date(2024, 10, 17))
    resultat = depot.enregistrer_collecte(
        session, _collecte(date_, ecarts=["amendement manquant : 2210"])
    )
    execution = session.get(ExecutionCollecte, resultat.execution_id)
    assert execution.statut == "ecart"
    assert execution.ecarts == ["amendement manquant : 2210"]
    assert execution.fin is not None


def test_charger_cibles_une_seule_fois(session):
    assert depot.charger_cibles(session) == 11
    assert depot.charger_cibles(session) == 0
    assert session.scalars(select(Cible).where(Cible.dispositif == "CII")).all()


def test_contrat_1_vers_2(session, archive_jorf):
    depot.enregistrer_collecte(session, jorf.lire_fichier(archive_jorf))
    paires = depot.pour_lot2(session).paires
    # Article 56 : 30 % -> 20 % (CII) et 2024 -> 2027 (CII) ; article 55 : L. 80 B (CIR et JEI).
    assert len(paires) == 4
    filtre, detecte = next(p for p in paires if p[1]["ancienne_valeur"] == "30 %")
    assert filtre["source"] == "legifrance" and filtre["type_texte"] == "loi"
    assert filtre["identifiants"] == {"nor": "ECOX0000000L"}
    assert detecte["dispositif"] == "CII" and detecte["parametre"] == "taux"
    assert detecte["article_vise"] == "article 244 quater B du code général des impôts"
    assert detecte["conditions"] == (
        "II. – Le 1° du I s'applique aux dépenses exposées à compter du 1er janvier 2025.",
    )

    # Le lot 2 accepte le changement assemblé, et retrouve notre empreinte.
    document = session.get(Document, filtre["identifiant"])
    ligne = session.get(ChangementExtrait, detecte["identifiant"])
    assemble = vers_lot2.assembler_pour_lot2(
        document.id, depot._brut(document), ligne.id, depot._schema(ligne)
    )
    changement = ChangementLot2.model_validate(assemble)
    assert changement.evenement == "publication"
    assert changement.empreinte_texte() == document.empreinte_texte


def test_format_attendu_par_entree_du_lot_2(session, archive_jorf):
    """S'exécute quand ``leypilot/mesure/entree.py`` (branche de P2) est fusionné."""
    entree = pytest.importorskip("leypilot.mesure.entree")
    depot.enregistrer_collecte(session, jorf.lire_fichier(archive_jorf))
    paires = depot.pour_lot2(session).paires
    documents = [entree.DocumentFiltre.model_validate(f) for f, _ in paires]
    changements = [entree.ChangementDetecte.model_validate(d) for _, d in paires]
    assembles, erreurs = entree.assembler_tous(documents, changements)
    assert erreurs == [] and len(assembles) == 4


def test_un_document_sans_date_n_est_jamais_ecarte_en_silence(session):
    """Revue de Papy : le cahier dit « jamais écarté en silence »."""
    resultat = depot.enregistrer_collecte(session, _collecte(_amendement(None, TEXTE)))
    execution = session.get(ExecutionCollecte, resultat.execution_id)
    assert execution.statut == "ecart"
    assert execution.ecarts == [
        "AN AMANR5L17PO59048B0324P0D1N002211 : document sans date, "
        "ses changements ne peuvent pas partir vers le lot 2"
    ]
    livraison = depot.pour_lot2(session)
    assert livraison.paires == []
    assert livraison.retenus == [
        (resultat.changements[0], "document sans date : le lot 2 ne peut pas dater l'étape")
    ]


def test_adoption_d_un_ancien_amendement_la_nuit_suivante(session, tmp_path):
    """Revue de Papy : déposé en octobre, adopté la veille ; la nuit suivante, le lot 2
    reçoit l'adoption, datée du vote."""
    from aide_collecte import fabriquer_archive_an

    from leypilot.collecte.sources import assemblee

    premier = assemblee.lire_archive(fabriquer_archive_an(tmp_path, sort_2211=None))
    depot.enregistrer_collecte(session, premier)
    deja = max(
        c for _, c in [(0, 0), *[(0, d["identifiant"]) for _, d in depot.pour_lot2(session).paires]]
    )

    nuit = assemblee.lire_archive(fabriquer_archive_an(tmp_path, sort_2211="Adopté"))
    depot.enregistrer_collecte(session, nuit)
    (filtre, detecte), *_ = depot.pour_lot2(session, deja).paires
    assert filtre["etape"] == "adoption"
    assert str(filtre["date_document"]) == "2024-10-25"
    assert (detecte["ancienne_valeur"], detecte["nouvelle_valeur"]) == ("30 %", "20 %")
