"""Chaîne du lot 2 : un changement (S2) → mesure rattachée, qualifiée, datée et résumée.

Appelé chaque nuit par la planification (P5) sur les nouveaux changements :

    suivi = SuiviMesures(session)
    for changement in changements:
        suivi.traiter(changement)
    suivi.appliquer_entrees_en_vigueur(date.today())
    session.commit()

Le suivi ne fait jamais de commit : c'est l'appelant qui valide la transaction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from leypilot.commun.base import maintenant
from leypilot.commun.llm import ServiceLLM
from leypilot.commun.modeles.mesure import (
    Mesure,
    RattachementAValider,
    ResumeMesure,
    TransitionMesure,
)
from leypilot.mesure.dates import DateVigueur, dater
from leypilot.mesure.etats import (
    STATUTS_FINAUX,
    TransitionInterdite,
    prochain_statut,
    statut_initial,
)
from leypilot.mesure.rattachement import (
    SEUIL_AUTO,
    SEUIL_HUMAIN,
    CandidatMesure,
    DecisionRattachement,
    Methode,
    rattacher,
)
from leypilot.mesure.resume import ResumeurS3
from leypilot.mesure.schemas import (
    Changement,
    Dispositif,
    Evenement,
    IdentifiantsOfficiels,
    NatureDate,
    StatutMesure,
)

journal = logging.getLogger(__name__)


@dataclass
class ResultatTraitement:
    changement_id: int
    mesure_id: int | None = None
    nouvelle_mesure: bool = False
    statut: StatutMesure | None = None
    transition: StatutMesure | None = None
    resume_id: int | None = None
    date_vigueur: DateVigueur | None = None
    en_attente_id: int | None = None
    erreurs: list[str] = field(default_factory=list)


class RattachementIntrouvable(LookupError):
    pass


class SuiviMesures:
    def __init__(
        self,
        session: Session,
        resumeur: ResumeurS3 | None = None,
        service_llm: ServiceLLM | None = None,
        seuil_auto: float = SEUIL_AUTO,
        seuil_humain: float = SEUIL_HUMAIN,
    ) -> None:
        self.session = session
        self.resumeur = resumeur or ResumeurS3()
        self.service_llm = service_llm
        self.seuil_auto = seuil_auto
        self.seuil_humain = seuil_humain

    # --- Point d'entrée -------------------------------------------------------------

    def traiter(
        self,
        changement: Changement,
        *,
        mesure_imposee: int | None = None,
        forcer_nouvelle: bool = False,
    ) -> ResultatTraitement:
        resultat = ResultatTraitement(changement_id=changement.identifiant)
        decision = self._decider(changement, mesure_imposee, forcer_nouvelle)

        if decision.a_valider:
            attente = RattachementAValider(
                changement_id=changement.identifiant,
                changement_json=changement.model_dump_json(),
                mesure_candidate_id=decision.mesure_id,
                score=decision.score,
            )
            self.session.add(attente)
            self.session.flush()
            resultat.en_attente_id = attente.id
            journal.info(
                "A2 : rattachement ambigu (score %.0f), soumis à un humain.", decision.score
            )
            return resultat

        if decision.nouvelle_mesure:
            mesure = self._creer_mesure(changement, resultat)
            if mesure is None:
                return resultat
            resultat.nouvelle_mesure = True
        else:
            mesure = self.session.get(Mesure, decision.mesure_id)
            if mesure is None:
                raise RattachementIntrouvable(f"Mesure {decision.mesure_id} introuvable.")
            self._completer_identifiants(mesure, changement)
            self._appliquer_evenement(mesure, changement, resultat)

        self.session.flush()
        resultat.mesure_id = mesure.id
        resultat.date_vigueur = self._dater(mesure, changement)
        resultat.resume_id = self._resumer(mesure, changement, resultat.date_vigueur).id
        resultat.statut = mesure.statut
        return resultat

    # --- A2 : rattachement --------------------------------------------------------

    def _decider(
        self, changement: Changement, mesure_imposee: int | None, forcer_nouvelle: bool
    ) -> DecisionRattachement:
        if forcer_nouvelle:
            return DecisionRattachement.nouvelle()
        if mesure_imposee is not None:
            return DecisionRattachement(mesure_imposee, Methode.HUMAIN, 100.0)
        return rattacher(
            changement,
            self.candidats(changement.dispositif),
            seuil_auto=self.seuil_auto,
            seuil_humain=self.seuil_humain,
        )

    def candidats(self, dispositif: Dispositif) -> list[CandidatMesure]:
        mesures = self.session.scalars(
            select(Mesure).where(
                Mesure.dispositif == dispositif, Mesure.statut.not_in(list(STATUTS_FINAUX))
            )
        )
        return [
            CandidatMesure(
                id=m.id,
                dispositif=m.dispositif,
                article_vise=m.article_vise,
                parametre=m.parametre,
                statut=m.statut,
                identifiants=IdentifiantsOfficiels(
                    dossier_legislatif=m.dossier_legislatif, nor=m.nor, eli=m.eli
                ),
                numeros_amendement=frozenset(m.numeros_amendement or []),
            )
            for m in mesures
        ]

    def rattachements_en_attente(self) -> list[RattachementAValider]:
        return list(
            self.session.scalars(
                select(RattachementAValider)
                .where(RattachementAValider.decision.is_(None))
                .order_by(RattachementAValider.id)
            )
        )

    def confirmer_rattachement(self, attente_id: int) -> ResultatTraitement:
        attente = self._attente(attente_id)
        resultat = self.traiter(
            Changement.model_validate_json(attente.changement_json),
            mesure_imposee=attente.mesure_candidate_id,
        )
        self._clore(attente, "confirme")
        return resultat

    def refuser_rattachement(self, attente_id: int) -> ResultatTraitement:
        attente = self._attente(attente_id)
        resultat = self.traiter(
            Changement.model_validate_json(attente.changement_json), forcer_nouvelle=True
        )
        self._clore(attente, "refuse")
        return resultat

    def _attente(self, attente_id: int) -> RattachementAValider:
        attente = self.session.get(RattachementAValider, attente_id)
        if attente is None or attente.decision is not None:
            raise RattachementIntrouvable(f"Aucun rattachement en attente n° {attente_id}.")
        return attente

    def _clore(self, attente: RattachementAValider, decision: str) -> None:
        attente.decision = decision
        attente.traite_le = maintenant()
        self.session.flush()

    # --- A3 : statuts ---------------------------------------------------------------

    def _creer_mesure(self, changement: Changement, resultat: ResultatTraitement) -> Mesure | None:
        try:
            statut = statut_initial(changement.evenement)
        except TransitionInterdite as erreur:
            resultat.erreurs.append(f"{erreur} Changement ignoré : aucune mesure connue.")
            return None
        ids = changement.identifiants
        mesure = Mesure(
            dispositif=changement.dispositif,
            article_vise=changement.article_vise,
            parametre=changement.parametre,
            statut=statut,
            dossier_legislatif=ids.dossier_legislatif,
            numeros_amendement=[ids.numero_amendement] if ids.numero_amendement else [],
            nor=ids.nor,
            eli=ids.eli,
            date_publication=(changement.date_document if statut == StatutMesure.PUBLIEE else None),
        )
        self.session.add(mesure)
        self._transition_depuis(mesure, None, statut, changement)
        resultat.transition = statut
        return mesure

    def _appliquer_evenement(
        self, mesure: Mesure, changement: Changement, resultat: ResultatTraitement
    ) -> None:
        try:
            nouveau = prochain_statut(mesure.statut, changement.evenement)
        except TransitionInterdite as erreur:
            mesure.a_revoir = True
            mesure.motif_a_revoir = str(erreur)
            resultat.erreurs.append(str(erreur))
            journal.warning("A3 : %s (mesure %s).", erreur, mesure.id)
            return
        if nouveau is None:
            return
        self._transition_depuis(mesure, mesure.statut, nouveau, changement)
        mesure.statut = nouveau
        resultat.transition = nouveau
        if nouveau == StatutMesure.PUBLIEE:
            mesure.date_publication = changement.date_document

    def _ajouter_transition(
        self,
        mesure: Mesure,
        de: StatutMesure | None,
        vers: StatutMesure,
        evenement: Evenement,
        jour: date,
        changement: Changement | None = None,
    ) -> None:
        mesure.transitions.append(
            TransitionMesure(
                de_statut=de,
                vers_statut=vers,
                evenement=evenement,
                date_evenement=jour,
                changement_id=changement.identifiant if changement else None,
                document_id=changement.document_id if changement else None,
            )
        )

    def _transition_depuis(
        self,
        mesure: Mesure,
        de: StatutMesure | None,
        vers: StatutMesure,
        changement: Changement,
    ) -> None:
        self._ajouter_transition(
            mesure, de, vers, changement.evenement, changement.date_document, changement
        )

    def _completer_identifiants(self, mesure: Mesure, changement: Changement) -> None:
        ids = changement.identifiants
        mesure.dossier_legislatif = mesure.dossier_legislatif or ids.dossier_legislatif
        mesure.nor = mesure.nor or ids.nor
        mesure.eli = mesure.eli or ids.eli
        numeros = list(mesure.numeros_amendement or [])
        if ids.numero_amendement and ids.numero_amendement not in numeros:
            mesure.numeros_amendement = [*numeros, ids.numero_amendement]

    def appliquer_entrees_en_vigueur(self, aujourd_hui: date) -> list[int]:
        """Passe en « appliquée » les mesures publiées dont la date est atteinte."""
        mesures = self.session.scalars(
            select(Mesure).where(
                Mesure.statut == StatutMesure.PUBLIEE,
                Mesure.date_entree_vigueur.is_not(None),
                Mesure.date_entree_vigueur <= aujourd_hui,
            )
        ).all()
        for mesure in mesures:
            if mesure.date_entree_vigueur is None:  # exclu par la requête ; garde pour le typage
                continue
            self._ajouter_transition(
                mesure,
                StatutMesure.PUBLIEE,
                StatutMesure.APPLIQUEE,
                Evenement.ENTREE_EN_VIGUEUR,
                mesure.date_entree_vigueur,
            )
            mesure.statut = StatutMesure.APPLIQUEE
        self.session.flush()
        return [m.id for m in mesures]

    # --- A4 : dates --------------------------------------------------------------

    def _dater(self, mesure: Mesure, changement: Changement) -> DateVigueur | None:
        trouvee = dater(
            changement, date_publication=mesure.date_publication, service_llm=self.service_llm
        )
        if trouvee is None:
            return None
        deja_certaine = mesure.nature_date == NatureDate.CERTAINE
        if trouvee.nature == NatureDate.CERTAINE or not deja_certaine:
            mesure.date_entree_vigueur = trouvee.date
            mesure.nature_date = trouvee.nature
            mesure.clause_entree_vigueur = trouvee.clause
        return trouvee

    # --- S3 : résumé --------------------------------------------------------------

    def _resumer(
        self, mesure: Mesure, changement: Changement, date_vigueur: DateVigueur | None
    ) -> ResumeMesure:
        existant = self.session.scalar(
            select(ResumeMesure).where(
                ResumeMesure.empreinte_texte == changement.empreinte_texte(),
                ResumeMesure.empreinte_changement == changement.empreinte_changement(),
                ResumeMesure.version == self.resumeur.version,
            )
        )
        if existant is not None:
            if existant.mesure_id is None:
                existant.mesure_id = mesure.id
            return existant

        produit = self.resumeur.resumer(changement, date_vigueur)
        resume = ResumeMesure(
            mesure_id=mesure.id,
            changement_id=changement.identifiant,
            empreinte_texte=changement.empreinte_texte(),
            empreinte_changement=changement.empreinte_changement(),
            version=produit.version,
            methode=produit.methode,
            texte=produit.texte,
            citation=produit.citation,
            a_verifier=produit.a_verifier,
            motifs_verification=produit.motifs,
        )
        self.session.add(resume)
        self.session.flush()
        return resume
