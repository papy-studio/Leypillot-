"""Contrat de sortie P2 → P3 : les mesures, en lecture seule.

D'après la répartition, le lot 2 fournit à la personne 3 les mesures : dispositif,
paramètre et conditions repris des changements, statut, date d'entrée en vigueur
et résumé. Les données descendent en cascade : la personne 4 ne lit pas les
mesures, elle reçoit ce qu'il lui faut (niveau, date, résumé) à travers les
impacts de la personne 3.

- ``mesures_modifiees_depuis`` : les mesures à (re)chiffrer depuis le dernier passage.
- ``mesures_publiees_depuis`` : les mesures publiées au JO, déclencheur de M3.
- ``vue_mesure`` : une mesure, par son identifiant (aussi pour l'historique affiché par P5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from leypilot.commun.modeles.mesure import Mesure, ResumeMesure, TransitionMesure
from leypilot.mesure.dates import jours_restants
from leypilot.mesure.graduation import Niveau, niveau
from leypilot.mesure.schemas import Dispositif, NatureDate, StatutMesure


@dataclass(frozen=True)
class VueMesure:
    """Une mesure telle que la personne 3 la reçoit."""

    id: int
    dispositif: Dispositif
    article_vise: str
    parametre: str
    ancienne_valeur: str | None
    nouvelle_valeur: str | None
    conditions: tuple[str, ...]
    statut: StatutMesure
    niveau: Niveau  # information (proposée) ou action (au moins votée, A5)
    date_publication: date | None
    date_entree_vigueur: date | None
    nature_date: NatureDate | None
    clause_entree_vigueur: str | None
    jours_restants: int | None
    resume: str | None
    citation: str | None
    a_verifier: bool
    resume_en_attente: bool  # LLM en échec : résumé provisoire, relancé plus tard
    a_revoir: bool
    documents: tuple[int, ...]  # documents du lot 1, dans l'ordre de la procédure
    maj_le: datetime


def dernier_resume(session: Session, mesure_id: int) -> ResumeMesure | None:
    return session.scalar(
        select(ResumeMesure)
        .where(ResumeMesure.mesure_id == mesure_id)
        .order_by(ResumeMesure.id.desc())
        .limit(1)
    )


def _vue(session: Session, mesure: Mesure, aujourd_hui: date) -> VueMesure:
    resume = dernier_resume(session, mesure.id)
    return VueMesure(
        id=mesure.id,
        dispositif=mesure.dispositif,
        article_vise=mesure.article_vise,
        parametre=mesure.parametre,
        ancienne_valeur=mesure.ancienne_valeur,
        nouvelle_valeur=mesure.nouvelle_valeur,
        conditions=tuple(mesure.conditions or ()),
        statut=mesure.statut,
        niveau=niveau(mesure.statut),
        date_publication=mesure.date_publication,
        date_entree_vigueur=mesure.date_entree_vigueur,
        nature_date=mesure.nature_date,
        clause_entree_vigueur=mesure.clause_entree_vigueur,
        jours_restants=(
            jours_restants(mesure.date_entree_vigueur, aujourd_hui)
            if mesure.date_entree_vigueur
            else None
        ),
        resume=resume.texte if resume else None,
        citation=resume.citation if resume else None,
        a_verifier=bool(resume and resume.a_verifier),
        resume_en_attente=bool(resume and resume.en_attente),
        a_revoir=mesure.a_revoir,
        documents=tuple(version.document_id for version in mesure.versions),
        maj_le=mesure.maj_le,
    )


def vue_mesure(
    session: Session, mesure_id: int, aujourd_hui: date | None = None
) -> VueMesure | None:
    mesure = session.get(Mesure, mesure_id)
    if mesure is None:
        return None
    return _vue(session, mesure, aujourd_hui or date.today())


def mesures_modifiees_depuis(
    session: Session, depuis: datetime, aujourd_hui: date | None = None
) -> list[VueMesure]:
    """Mesures créées ou modifiées depuis ``depuis`` : nouveau changement, nouveau
    statut, nouvelle date, résumé refait. Point d'entrée du chiffrage (P3)."""
    mesures = session.scalars(
        select(Mesure).where(Mesure.maj_le >= depuis).order_by(Mesure.id)
    ).all()
    aujourd_hui = aujourd_hui or date.today()
    return [_vue(session, mesure, aujourd_hui) for mesure in mesures]


def mesures_publiees_depuis(session: Session, depuis: datetime) -> list[Mesure]:
    """Mesures passées au statut « publiée » depuis ``depuis`` (déclencheur de M3)."""
    return list(
        session.scalars(
            select(Mesure)
            .join(TransitionMesure, TransitionMesure.mesure_id == Mesure.id)
            .where(
                TransitionMesure.vers_statut == StatutMesure.PUBLIEE,
                TransitionMesure.cree_le >= depuis,
            )
            .distinct()
            .order_by(Mesure.id)
        )
    )
