"""Contrat 1 → 2 : ce que le lot 1 transmet à la personne 2.

Deux formats, qui suivent ``leypilot.mesure.entree`` (lot 2) champ par champ :

- ``document_filtre`` : un document retenu (``DocumentFiltre``) ;
- ``changement_detecte`` : un changement rattaché à un dispositif (``ChangementDetecte``).

``assembler_pour_lot2`` fait directement l'assemblage des deux en un ``Changement`` du
lot 2, pour le fil rouge et tant que ``entree.py`` n'est pas fusionné dans ``main``.

Règles :
- seuls les changements rattachés à un dispositif (CIR, CII, JEI) partent vers le lot 2 ;
  les autres restent dans la table ``changement`` (indicateurs, file « à revoir ») ;
- ``texte_source`` est ``document.texte`` (normalisé) : son SHA-256 côté lot 2 est égal
  à ``document.empreinte_texte`` ;
- les clauses d'application partent telles quelles dans ``conditions``.
"""

from __future__ import annotations

from typing import Any

from leypilot.collecte.schemas import Changement, Statut
from leypilot.collecte.sources.base import DocumentBrut, Source, TypeTexte

SOURCES_LOT2 = {
    Source.JORF: "legifrance",
    Source.LEGI: "legifrance",
    Source.AN: "assemblee",
    Source.SENAT: "senat",
    Source.BOFIP: "bofip",
}
# Types que le lot 2 sait traiter aujourd'hui (``entree.TypeTexte``).
TYPES_LOT2 = {t.value for t in TypeTexte} - {TypeTexte.VERSION_CONSOLIDEE.value}
DETERMINANTS = ("le ", "la ", "les ", "l'")


def article_vise(changement: Changement) -> str | None:
    """« 244 quater B » + « code général des impôts » → « article 244 quater B du code
    général des impôts »."""
    if not changement.article:
        return None
    if not changement.code:
        return f"article {changement.article}"
    liaison = "de la" if changement.code.startswith("loi") else "du"
    return f"article {changement.article} {liaison} {changement.code}"


def parametre(changement: Changement) -> str:
    """Nom du paramètre : celui de la personne 3 s'il est connu, sinon l'objet de la
    formule sans déterminant (« taux », « année »), sinon le type d'opération."""
    if changement.parametre:
        return changement.parametre
    objet = (changement.objet or "").strip().lower()
    for determinant in DETERMINANTS:
        if objet.startswith(determinant):
            objet = objet[len(determinant) :]
            break
    return objet or changement.operation.value


def document_filtre(document_id: int, document: DocumentBrut) -> dict[str, Any] | None:
    """Format ``DocumentFiltre`` du lot 2 ; ``None`` si le lot 2 ne traite pas ce type."""
    if document.type_texte.value not in TYPES_LOT2 or document.date_document is None:
        return None
    identifiants = {
        "dossier_legislatif": document.dossier_legislatif,
        "numero_amendement": document.numero_amendement,
        "nor": document.nor,
        "eli": document.eli,
    }
    return {
        "identifiant": document_id,
        "source": SOURCES_LOT2[document.source],
        "type_texte": document.type_texte.value,
        "date_document": document.date_document,
        "texte": document.texte,
        "identifiants": {k: v for k, v in identifiants.items() if v},
        "etape": document.etape,
    }


def changement_detecte(changement_id: int, changement: Changement) -> dict[str, Any] | None:
    """Format ``ChangementDetecte`` du lot 2 ; ``None`` si aucun dispositif n'est touché."""
    if changement.dispositif not in {"CIR", "CII", "JEI"}:
        return None
    return {
        "identifiant": changement_id,
        "document_id": changement.document_id,
        "dispositif": changement.dispositif,
        "parametre": parametre(changement),
        "ancienne_valeur": changement.ancienne_valeur,
        "nouvelle_valeur": changement.nouvelle_valeur,
        "passage_cite": changement.passage.texte,
        "article_vise": article_vise(changement),
        "conditions": tuple(changement.clauses_application),
        "a_revoir": changement.statut == Statut.A_REVOIR,
    }


ETAPES_PAR_TYPE = {
    "projet_loi": "depot",
    "proposition_loi": "depot",
    "amendement": "depot",
    "texte_adopte": "adoption",
}


def assembler_pour_lot2(
    document_id: int, document: DocumentBrut, changement_id: int, changement: Changement
) -> dict[str, Any] | None:
    """``Changement`` du lot 2 (``leypilot.mesure.schemas.Changement``), prêt à valider."""
    filtre = document_filtre(document_id, document)
    detecte = changement_detecte(changement_id, changement)
    if filtre is None or detecte is None:
        return None
    etape = filtre["etape"] or ETAPES_PAR_TYPE.get(filtre["type_texte"], "publication")
    return {
        "identifiant": changement_id,
        "document_id": document_id,
        "evenement": etape,
        "date_document": filtre["date_document"],
        "dispositif": detecte["dispositif"],
        "article_vise": detecte["article_vise"] or "",
        "parametre": detecte["parametre"],
        "ancienne_valeur": detecte["ancienne_valeur"],
        "nouvelle_valeur": detecte["nouvelle_valeur"],
        "passage_cite": detecte["passage_cite"],
        "texte_source": filtre["texte"],
        "a_revoir": detecte["a_revoir"],
        "identifiants": filtre["identifiants"],
        "conditions": detecte["conditions"],
    }
