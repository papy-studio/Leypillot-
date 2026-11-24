"""Ce que le lot 2 fournit aux autres lots, en lecture seule.

- P3 (Chiffrer) : ``mesures_publiees_depuis`` déclenche M3 (brouillon de règle).
- P4 (Alerter) : ``vue_mesure`` donne statut, niveau, date, compte à rebours et
  résumé ; ``Mesure.id`` sert de clé de regroupement des alertes.
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
    id: int
    dispositif: Dispositif
    article_vise: str
    parametre: str
    statut: StatutMesure
    niveau: Niveau
    date_entree_vigueur: date | None
    nature_date: NatureDate | None
    jours_restants: int | None
    resume: str | None
    citation: str | None
    a_verifier: bool
    a_revoir: bool


def dernier_resume(session: Session, mesure_id: int) -> ResumeMesure | None:
    return session.scalar(
        select(ResumeMesure)
        .where(ResumeMesure.mesure_id == mesure_id)
        .order_by(ResumeMesure.id.desc())
        .limit(1)
    )


def vue_mesure(
    session: Session, mesure_id: int, aujourd_hui: date | None = None
) -> VueMesure | None:
    mesure = session.get(Mesure, mesure_id)
    if mesure is None:
        return None
    aujourd_hui = aujourd_hui or date.today()
    resume = dernier_resume(session, mesure_id)
    return VueMesure(
        id=mesure.id,
        dispositif=mesure.dispositif,
        article_vise=mesure.article_vise,
        parametre=mesure.parametre,
        statut=mesure.statut,
        niveau=niveau(mesure.statut),
        date_entree_vigueur=mesure.date_entree_vigueur,
        nature_date=mesure.nature_date,
        jours_restants=(
            jours_restants(mesure.date_entree_vigueur, aujourd_hui)
            if mesure.date_entree_vigueur
            else None
        ),
        resume=resume.texte if resume else None,
        citation=resume.citation if resume else None,
        a_verifier=bool(resume and resume.a_verifier),
        a_revoir=mesure.a_revoir,
    )


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
