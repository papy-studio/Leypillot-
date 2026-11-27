"""A3 · Qualifier : machine à états de la mesure.

Parcours : Proposée → Votée → Publiée → Appliquée, plus Abandonnée (rejet,
suppression ou censure). Seules les transitions de ``TRANSITIONS`` sont
permises ; chacune est déclenchée par un événement de la source.

« Votée » veut dire texte définitivement adopté : c'est à partir de là que des
actions sont permises (A5). L'adoption d'un amendement en séance ne change pas
le statut : la mesure reste proposée, l'étape est gardée dans ``version_mesure``.

Points ouverts (cahier technique) : statut « En attente de décret » et cycle
propre au BOFiP. Ils s'ajouteront ici sans toucher au reste.
"""

from __future__ import annotations

from leypilot.mesure.schemas import Evenement, StatutMesure

S = StatutMesure

TRANSITIONS: dict[StatutMesure, frozenset[StatutMesure]] = {
    S.PROPOSEE: frozenset({S.VOTEE, S.ABANDONNEE}),
    S.VOTEE: frozenset({S.PUBLIEE, S.ABANDONNEE}),  # censure du Conseil constitutionnel
    S.PUBLIEE: frozenset({S.APPLIQUEE}),
    S.APPLIQUEE: frozenset(),
    S.ABANDONNEE: frozenset(),
}

STATUT_APRES: dict[Evenement, StatutMesure] = {
    Evenement.DEPOT: S.PROPOSEE,
    Evenement.ADOPTION: S.VOTEE,
    Evenement.ADOPTION_AMENDEMENT: S.PROPOSEE,  # statut initial seulement
    Evenement.PUBLICATION: S.PUBLIEE,
    Evenement.ENTREE_EN_VIGUEUR: S.APPLIQUEE,
    Evenement.REJET: S.ABANDONNEE,
    Evenement.SUPPRESSION: S.ABANDONNEE,
    Evenement.CENSURE: S.ABANDONNEE,
}

# Statuts possibles à la création : un texte réglementaire (décret, arrêté) arrive
# directement publié ; une mesure peut aussi être repérée au moment du vote.
STATUTS_INITIAUX = frozenset({S.PROPOSEE, S.VOTEE, S.PUBLIEE})
STATUTS_FINAUX = frozenset({S.APPLIQUEE, S.ABANDONNEE})

# Événements qui complètent une mesure sans jamais changer son statut.
EVENEMENTS_SANS_TRANSITION = frozenset({Evenement.ADOPTION_AMENDEMENT})


class TransitionInterdite(ValueError):
    pass


def statut_initial(evenement: Evenement) -> StatutMesure:
    statut = STATUT_APRES[evenement]
    if statut not in STATUTS_INITIAUX:
        raise TransitionInterdite(
            f"Une mesure ne peut pas commencer par l'événement « {evenement} »."
        )
    return statut


def prochain_statut(actuel: StatutMesure, evenement: Evenement) -> StatutMesure | None:
    """Statut après l'événement ; ``None`` si l'événement confirme le statut actuel
    ou ne change jamais le statut (amendement adopté en séance)."""
    if evenement in EVENEMENTS_SANS_TRANSITION:
        return None
    cible = STATUT_APRES[evenement]
    if cible == actuel:
        return None
    if cible not in TRANSITIONS[actuel]:
        raise TransitionInterdite(
            f"Transition interdite : {actuel} → {cible} (événement « {evenement} »)."
        )
    return cible
