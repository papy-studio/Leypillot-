"""A2 · Relier : rattacher un changement à la mesure qu'il fait évoluer.

Une mesure regroupe toutes les versions d'une même modification (amendement,
texte adopté, loi publiée). Ordre des règles :

1. même numéro d'amendement → même mesure ;
2. sinon, parmi les mesures en cours du même dispositif et du même article,
   ``rapidfuzz`` compare l'article visé et le paramètre modifié :
   - score ≥ ``seuil_auto`` → rattachement automatique ;
   - ``seuil_humain`` ≤ score < ``seuil_auto`` → soumis à un humain ;
   - en dessous → nouvelle mesure.
   Un identifiant de texte commun (dossier législatif, NOR, ELI) fait passer
   un score de la zone humaine en automatique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from rapidfuzz import fuzz

from leypilot.mesure.etats import STATUTS_FINAUX
from leypilot.mesure.schemas import Changement, Dispositif, IdentifiantsOfficiels, StatutMesure
from leypilot.mesure.textes import normaliser_article, normaliser_libelle, noyau_article

SEUIL_AUTO = 90.0
SEUIL_HUMAIN = 70.0
POIDS_ARTICLE = 0.5


class Methode(StrEnum):
    AMENDEMENT = "amendement"
    SIMILARITE = "similarite"
    HUMAIN = "humain"
    AUCUNE = "aucune"


@dataclass(frozen=True)
class CandidatMesure:
    id: int
    dispositif: Dispositif
    article_vise: str
    parametre: str
    statut: StatutMesure
    identifiants: IdentifiantsOfficiels = field(default_factory=IdentifiantsOfficiels)
    numeros_amendement: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DecisionRattachement:
    mesure_id: int | None
    methode: Methode
    score: float
    a_valider: bool = False

    @property
    def nouvelle_mesure(self) -> bool:
        return self.mesure_id is None

    @classmethod
    def nouvelle(cls, score: float = 0.0) -> DecisionRattachement:
        return cls(None, Methode.AUCUNE, score)


def score_similarite(changement: Changement, candidat: CandidatMesure) -> float:
    score_article = fuzz.token_set_ratio(
        normaliser_article(changement.article_vise), normaliser_article(candidat.article_vise)
    )
    score_parametre = fuzz.token_set_ratio(
        normaliser_libelle(changement.parametre), normaliser_libelle(candidat.parametre)
    )
    return POIDS_ARTICLE * score_article + (1 - POIDS_ARTICLE) * score_parametre


def _texte_commun(a: IdentifiantsOfficiels, b: IdentifiantsOfficiels) -> bool:
    ids_a, ids_b = a.identifiants_texte(), b.identifiants_texte()
    return any(ids_b.get(cle) == valeur for cle, valeur in ids_a.items())


def _texte_different(a: IdentifiantsOfficiels, b: IdentifiantsOfficiels) -> bool:
    """Deux dossiers législatifs connus et différents : ce n'est pas la même mesure."""
    return bool(
        a.dossier_legislatif
        and b.dossier_legislatif
        and a.dossier_legislatif != b.dossier_legislatif
    )


def candidats_compatibles(
    changement: Changement, candidats: list[CandidatMesure]
) -> list[CandidatMesure]:
    noyau = noyau_article(changement.article_vise)
    retenus = []
    for candidat in candidats:
        if candidat.dispositif != changement.dispositif or candidat.statut in STATUTS_FINAUX:
            continue
        if _texte_different(changement.identifiants, candidat.identifiants):
            continue
        noyau_candidat = noyau_article(candidat.article_vise)
        if noyau and noyau_candidat and noyau != noyau_candidat:
            continue  # 244 quater B (CII) n'est pas 44 sexies-0 A (JEI)
        retenus.append(candidat)
    return retenus


def rattacher(
    changement: Changement,
    candidats: list[CandidatMesure],
    *,
    seuil_auto: float = SEUIL_AUTO,
    seuil_humain: float = SEUIL_HUMAIN,
) -> DecisionRattachement:
    compatibles = candidats_compatibles(changement, candidats)

    amendement = changement.identifiants.numero_amendement
    if amendement:
        for candidat in compatibles:
            if amendement in candidat.numeros_amendement:
                return DecisionRattachement(candidat.id, Methode.AMENDEMENT, 100.0)

    meilleur: CandidatMesure | None = None
    meilleur_score = 0.0
    for candidat in compatibles:
        score = score_similarite(changement, candidat)
        if score > meilleur_score:
            meilleur, meilleur_score = candidat, score

    if meilleur is None or meilleur_score < seuil_humain:
        return DecisionRattachement.nouvelle(meilleur_score)
    if meilleur_score >= seuil_auto or _texte_commun(
        changement.identifiants, meilleur.identifiants
    ):
        return DecisionRattachement(meilleur.id, Methode.SIMILARITE, meilleur_score)
    return DecisionRattachement(meilleur.id, Methode.SIMILARITE, meilleur_score, a_valider=True)
