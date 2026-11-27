"""S2 · Extraction de secours : une ligne qui touche un article suivi sans formule reconnue.

Sans LLM (ou si le LLM échoue), la ligne devient un changement « à revoir » de type
``non_reconnue``, motif ``aucune_formule`` : un humain la lit dans la file « à revoir ».

Avec le LLM (``ServiceLLM`` de la personne 2, prompt ``s2_secours``), on lui demande
l'opération et les valeurs, puis on vérifie tout mot pour mot. Le résultat reste
« à revoir » (motif ``extraction_llm``) : le LLM ne produit jamais un changement « ok »
dans le MVP. Le choix du modèle et le budget appartiennent à la personne 2.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from leypilot.collecte.cibles import rattacher
from leypilot.collecte.formules import LigneSansFormule
from leypilot.collecte.schemas import Changement, Methode, Motif, Operation, Passage, Statut
from leypilot.commun.llm import ErreurLLM, ReponseInvalide, ServiceLLM

journal = logging.getLogger(__name__)

PROMPT = "s2_secours"
VERSION_PROMPT = "v1"

OPERATIONS_LLM = {
    "remplacement": Operation.REMPLACEMENT,
    "insertion": Operation.INSERTION_MOTS,
    "suppression": Operation.SUPPRESSION_MOTS,
    "redaction": Operation.REDACTION,
}


class LectureSecours(BaseModel):
    """Réponse attendue du LLM (prompt ``s2_secours``)."""

    modifie: bool
    operation: str | None = None
    objet: str | None = None
    ancienne_valeur: str | None = None
    nouvelle_valeur: str | None = None
    passage: str | None = None


def _passage(document_id: int, texte_document: str, extrait: str) -> Passage | None:
    debut = texte_document.find(extrait)
    if debut < 0:
        return None
    return Passage(document_id=document_id, debut=debut, fin=debut + len(extrait), texte=extrait)


def _changement_a_lire(
    ligne: LigneSansFormule, document_id: int, texte_document: str, dispositif: str
) -> Changement:
    passage = _passage(document_id, texte_document, ligne.ligne)
    motifs = [Motif.AUCUNE_FORMULE]
    if passage is None:
        motifs.append(Motif.PASSAGE_INTROUVABLE)
        passage = Passage(document_id=document_id, debut=0, fin=len(ligne.ligne), texte=ligne.ligne)
    return Changement(
        document_id=document_id,
        operation=Operation.NON_RECONNUE,
        code=ligne.code,
        article=ligne.article,
        localisation=ligne.localisation,
        dispositif=dispositif,
        passage=passage,
        methode=Methode.REGEX,
        clauses_application=ligne.clauses_application,
        statut=Statut.A_REVOIR,
        motifs=motifs,
    )


def _lecture_llm(
    service: ServiceLLM, ligne: LigneSansFormule, dispositif: str
) -> LectureSecours | None:
    try:
        return service.generer(
            PROMPT,
            LectureSecours,
            {
                "article": f"article {ligne.article} ({ligne.code})",
                "dispositif": dispositif,
                "localisation": ligne.localisation or "non précisé",
                "ligne": ligne.ligne,
            },
            version=VERSION_PROMPT,
        )
    except (ErreurLLM, ReponseInvalide) as erreur:  # LLMNonConfigure hérite d'ErreurLLM
        journal.info("Secours LLM indisponible pour %s : %s", ligne.article, erreur)
        return None


def lire_ligne(
    ligne: LigneSansFormule,
    document_id: int,
    texte_document: str,
    service: ServiceLLM | None = None,
) -> list[Changement]:
    """Un changement « à revoir » par dispositif touché par la ligne."""
    dispositifs = rattacher(ligne.articles, ligne.localisation, ligne.ligne)
    resultat = []
    for dispositif in dispositifs:
        par_defaut = _changement_a_lire(ligne, document_id, texte_document, dispositif)
        lecture = _lecture_llm(service, ligne, dispositif) if service else None
        if lecture is None or not lecture.modifie or not lecture.passage:
            resultat.append(par_defaut)
            continue
        passage = _passage(document_id, texte_document, lecture.passage)
        valeurs = (lecture.ancienne_valeur, lecture.nouvelle_valeur)
        verifie = (
            passage is not None
            and lecture.passage in ligne.ligne
            and all(v is None or v in lecture.passage for v in valeurs)
        )
        if not verifie or passage is None:
            journal.warning("Lecture LLM non recopiée mot pour mot : %s", ligne.ligne[:80])
            resultat.append(par_defaut)
            continue
        resultat.append(
            Changement.model_validate(
                par_defaut.model_dump()
                | {
                    "operation": OPERATIONS_LLM.get(
                        (lecture.operation or "").lower(), Operation.NON_RECONNUE
                    ),
                    "objet": lecture.objet,
                    "ancienne_valeur": lecture.ancienne_valeur,
                    "nouvelle_valeur": lecture.nouvelle_valeur,
                    "passage": passage,
                    "methode": Methode.LLM,
                    "motifs": [Motif.AUCUNE_FORMULE, Motif.EXTRACTION_LLM],
                }
            )
        )
    return resultat
