from datetime import UTC, date, datetime

import pytest

from leypilot.commun.llm import ClientFactice, ClientNonConfigure, ServiceLLM
from leypilot.commun.modeles.mesure import Mesure, ResumeMesure, VersionMesure
from leypilot.mesure.graduation import Niveau
from leypilot.mesure.requetes import (
    VueMesure,
    mesures_modifiees_depuis,
    mesures_publiees_depuis,
    vue_mesure,
)
from leypilot.mesure.resume import creer_resumeur
from leypilot.mesure.schemas import NatureDate, StatutMesure
from leypilot.mesure.suivi import RattachementIntrouvable, SuiviMesures

S = StatutMesure


def vue(session, mesure_id: int | None, aujourd_hui: date | None = None) -> VueMesure:
    """Vue d'une mesure qui doit exister (échoue clairement sinon)."""
    assert mesure_id is not None
    trouvee = vue_mesure(session, mesure_id, aujourd_hui)
    assert trouvee is not None
    return trouvee


def test_premier_changement_cree_la_mesure(session, fabrique):
    resultat = SuiviMesures(session).traiter(fabrique())

    mesure = session.get(Mesure, resultat.mesure_id)
    assert resultat.nouvelle_mesure
    assert mesure.statut == S.PROPOSEE
    assert mesure.date_entree_vigueur == date(2026, 1, 1)
    assert mesure.nature_date == NatureDate.CERTAINE
    assert [t.vers_statut for t in mesure.transitions] == [S.PROPOSEE]
    assert len(mesure.resumes) == 1


def test_parcours_complet_jusqu_a_l_application(session, fabrique):
    suivi = SuiviMesures(session)
    ids = {"dossier_legislatif": "PLF2026"}
    premier = suivi.traiter(fabrique(identifiant=1, identifiants=ids))
    suivi.traiter(
        fabrique(
            identifiant=2, evenement="adoption", date_document=date(2025, 12, 18), identifiants=ids
        )
    )
    suivi.traiter(
        fabrique(
            identifiant=3,
            evenement="publication",
            date_document=date(2025, 12, 31),
            identifiants=ids,
        )
    )

    assert suivi.appliquer_entrees_en_vigueur(date(2025, 12, 31)) == []
    assert suivi.appliquer_entrees_en_vigueur(date(2026, 1, 1)) == [premier.mesure_id]

    mesure = session.get(Mesure, premier.mesure_id)
    assert session.query(Mesure).count() == 1
    assert [t.vers_statut for t in mesure.transitions] == [
        S.PROPOSEE,
        S.VOTEE,
        S.PUBLIEE,
        S.APPLIQUEE,
    ]
    assert mesure.date_publication == date(2025, 12, 31)


def test_transition_interdite_marque_la_mesure_a_revoir(session, fabrique):
    suivi = SuiviMesures(session)
    premier = suivi.traiter(fabrique(identifiant=1))
    resultat = suivi.traiter(fabrique(identifiant=2, evenement="publication"))

    mesure = session.get(Mesure, premier.mesure_id)
    assert resultat.mesure_id == premier.mesure_id
    assert mesure.statut == S.PROPOSEE
    assert mesure.a_revoir
    assert resultat.erreurs


def test_rejet_d_une_mesure_inconnue_est_ignore(session, fabrique):
    resultat = SuiviMesures(session).traiter(fabrique(evenement="rejet"))
    assert resultat.mesure_id is None
    assert resultat.erreurs
    assert session.query(Mesure).count() == 0


def test_rattachement_ambigu_mis_en_attente_puis_confirme(session, fabrique):
    suivi = SuiviMesures(session, seuil_auto=99, seuil_humain=50)
    premier = suivi.traiter(fabrique(identifiant=1, parametre="taux du crédit d'impôt innovation"))
    ambigu = suivi.traiter(
        fabrique(identifiant=2, evenement="adoption", parametre="taux majoré outre-mer")
    )

    assert ambigu.en_attente_id is not None
    assert ambigu.mesure_id is None
    assert session.get(Mesure, premier.mesure_id).statut == S.PROPOSEE  # rien n'a bougé

    [attente] = suivi.rattachements_en_attente()
    confirme = suivi.confirmer_rattachement(attente.id)
    assert confirme.mesure_id == premier.mesure_id
    assert session.get(Mesure, premier.mesure_id).statut == S.VOTEE
    assert suivi.rattachements_en_attente() == []
    with pytest.raises(RattachementIntrouvable):
        suivi.confirmer_rattachement(attente.id)


def test_rattachement_refuse_cree_une_nouvelle_mesure(session, fabrique):
    suivi = SuiviMesures(session, seuil_auto=99, seuil_humain=50)
    suivi.traiter(fabrique(identifiant=1, parametre="taux du crédit d'impôt innovation"))
    ambigu = suivi.traiter(fabrique(identifiant=2, parametre="taux majoré outre-mer"))

    assert ambigu.en_attente_id is not None
    refuse = suivi.refuser_rattachement(ambigu.en_attente_id)
    assert refuse.nouvelle_mesure
    assert session.query(Mesure).count() == 2


def test_resume_jamais_refait_pour_le_meme_changement(session, fabrique):
    suivi = SuiviMesures(session)
    premier = suivi.traiter(fabrique(identifiant=1))
    second = suivi.traiter(fabrique(identifiant=1))
    assert premier.resume_id == second.resume_id
    assert session.query(ResumeMesure).count() == 1


def test_date_certaine_pas_ecrasee_par_une_estimation(session, fabrique):
    suivi = SuiviMesures(session)
    ids = {"dossier_legislatif": "PLF2026"}
    premier = suivi.traiter(fabrique(identifiant=1, identifiants=ids))
    suivi.traiter(fabrique(identifiant=2, evenement="adoption", identifiants=ids))
    sans_clause = "le taux : « 30 % » est remplacé par le taux : « 20 % » au k du II."
    suivi.traiter(
        fabrique(
            identifiant=3,
            evenement="publication",
            date_document=date(2025, 12, 31),
            identifiants=ids,
            texte_source=sans_clause,
        )
    )
    mesure = session.get(Mesure, premier.mesure_id)
    assert (mesure.date_entree_vigueur, mesure.nature_date) == (
        date(2026, 1, 1),
        NatureDate.CERTAINE,
    )


def test_vues_pour_les_lots_3_et_4(session, fabrique):
    debut = datetime(2000, 1, 1, tzinfo=UTC)
    suivi = SuiviMesures(session)
    premier = suivi.traiter(fabrique(identifiant=1))
    assert mesures_publiees_depuis(session, debut) == []

    etat = vue(session, premier.mesure_id, date(2025, 11, 20))
    assert etat.niveau == "information"
    assert etat.jours_restants == 42
    assert (etat.resume or "").startswith("CII :")
    assert vue_mesure(session, 999) is None

    suivi.traiter(fabrique(identifiant=2, evenement="adoption"))
    suivi.traiter(
        fabrique(identifiant=3, evenement="publication", date_document=date(2025, 12, 31))
    )
    assert [m.id for m in mesures_publiees_depuis(session, debut)] == [premier.mesure_id]
    assert vue(session, premier.mesure_id).niveau == "action"


# --- Contrat de sortie vers la personne 3 ------------------------------------------


def test_la_mesure_porte_les_valeurs_et_les_conditions(session, fabrique):
    suivi = SuiviMesures(session)
    ids = {"dossier_legislatif": "PLF2026"}
    premier = suivi.traiter(fabrique(identifiant=1, identifiants=ids, conditions=("PME",)))
    # Le texte voté retient 25 % au lieu des 20 % de l'amendement, avec une condition de plus.
    suivi.traiter(
        fabrique(
            identifiant=2,
            evenement="adoption",
            nouvelle_valeur="25 %",
            identifiants=ids,
            conditions=("PME", "dépenses exposées en France"),
        )
    )
    etat = vue(session, premier.mesure_id)
    assert (etat.ancienne_valeur, etat.nouvelle_valeur) == ("30 %", "25 %")
    assert etat.conditions == ("PME", "dépenses exposées en France")


def test_chaque_changement_laisse_une_version_reliee_a_son_document(session, fabrique):
    suivi = SuiviMesures(session)
    ids = {"dossier_legislatif": "PLF2026"}
    premier = suivi.traiter(fabrique(identifiant=1, document_id=10, identifiants=ids))
    suivi.traiter(fabrique(identifiant=2, document_id=20, evenement="adoption", identifiants=ids))
    suivi.traiter(fabrique(identifiant=2, document_id=20, evenement="adoption", identifiants=ids))

    versions = session.query(VersionMesure).order_by(VersionMesure.id).all()
    assert [(v.changement_id, v.document_id, v.methode) for v in versions] == [
        (1, 10, "creation"),
        (2, 20, "similarite"),
    ]
    assert vue(session, premier.mesure_id).documents == (10, 20)


def test_rattachement_confirme_par_un_humain_est_trace(session, fabrique):
    suivi = SuiviMesures(session, seuil_auto=99, seuil_humain=50)
    suivi.traiter(fabrique(identifiant=1, parametre="taux du crédit d'impôt innovation"))
    ambigu = suivi.traiter(
        fabrique(identifiant=2, evenement="adoption", parametre="taux majoré outre-mer")
    )
    assert ambigu.en_attente_id is not None
    suivi.confirmer_rattachement(ambigu.en_attente_id)
    version = session.query(VersionMesure).filter_by(changement_id=2).one()
    assert version.methode == "humain"


def test_mesures_modifiees_depuis_le_dernier_passage(session, fabrique):
    suivi = SuiviMesures(session)
    debut = datetime(2000, 1, 1, tzinfo=UTC)
    premier = suivi.traiter(fabrique(identifiant=1))
    session.flush()
    assert [m.id for m in mesures_modifiees_depuis(session, debut)] == [premier.mesure_id]
    futur = datetime(2999, 1, 1, tzinfo=UTC)
    assert mesures_modifiees_depuis(session, futur) == []


# --- Résumé en attente, relancé plus tard ------------------------------------------


def test_resume_en_attente_puis_relance(session, fabrique):
    en_panne = SuiviMesures(session, resumeur=creer_resumeur(ServiceLLM(ClientNonConfigure())))
    resultat = en_panne.traiter(fabrique(identifiant=1))
    etat = vue(session, resultat.mesure_id)
    assert etat.resume_en_attente
    assert (etat.resume or "").startswith("CII :")  # texte provisoire du gabarit

    # Toujours en panne : rien ne change.
    assert en_panne.relancer_resumes_en_attente() == []

    # Le LLM répond de nouveau.
    client = ClientFactice(
        {
            "s3_citation": [
                '{"citation": "le taux : « 30 % » est remplacé par le taux : « 20 % »"}'
            ],
            "s3_resume": [
                '{"resume": "Le taux du CII baisse de 30 % à 20 % au 1er janvier 2026."}'
            ],
        }
    )
    retabli = SuiviMesures(session, resumeur=creer_resumeur(ServiceLLM(client)))
    assert retabli.relancer_resumes_en_attente() == [resultat.mesure_id]

    etat = vue(session, resultat.mesure_id)
    assert not etat.resume_en_attente
    assert etat.resume == "Le taux du CII baisse de 30 % à 20 % au 1er janvier 2026."
    assert session.query(ResumeMesure).filter_by(en_attente=True).count() == 0
    assert retabli.relancer_resumes_en_attente() == []


def test_amendement_adopte_laisse_la_mesure_proposee(session, fabrique):
    suivi = SuiviMesures(session)
    ids = {"dossier_legislatif": "PLF2026", "numero_amendement": "I-1234"}
    premier = suivi.traiter(fabrique(identifiant=1, identifiants=ids))
    adopte = suivi.traiter(
        fabrique(
            identifiant=2,
            evenement="adoption_amendement",
            date_document=date(2025, 11, 5),
            identifiants=ids,
        )
    )

    assert premier.mesure_id is not None
    assert adopte.mesure_id == premier.mesure_id
    assert adopte.transition is None
    vue = vue_mesure(session, premier.mesure_id)
    assert vue is not None
    assert (vue.statut, vue.niveau, vue.amendement_adopte) == (
        S.PROPOSEE,
        Niveau.INFORMATION,
        True,
    )

    # Seul le texte définitivement adopté fait passer la mesure « votée ».
    vote = suivi.traiter(
        fabrique(
            identifiant=3,
            evenement="adoption",
            date_document=date(2025, 12, 18),
            identifiants={"dossier_legislatif": "PLF2026"},
        )
    )
    assert vote.transition == S.VOTEE
