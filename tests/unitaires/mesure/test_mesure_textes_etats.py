import pytest

from leypilot.mesure.etats import TransitionInterdite, prochain_statut, statut_initial
from leypilot.mesure.graduation import ActionInterdite, Niveau, niveau, verifier_action_autorisee
from leypilot.mesure.schemas import Evenement, StatutMesure
from leypilot.mesure.textes import (
    citation_verifiee,
    normaliser_article,
    noyau_article,
)

S, E = StatutMesure, Evenement

# --- Vérification mot pour mot ---------------------------------------------------


def test_citation_exacte_aux_espaces_et_apostrophes_pres():
    texte = "Le I s’applique aux dépenses exposées à compter du 1er janvier 2026."
    assert citation_verifiee("Le I s'applique aux dépenses exposées", texte)


def test_citation_reformulee_refusee():
    texte = "le taux : « 30 % » est remplacé par le taux : « 20 % »"
    assert not citation_verifiee("le taux de 30 % devient 20 %", texte)
    assert not citation_verifiee("", texte)
    assert not citation_verifiee("taux", texte)  # trop courte pour être une preuve


# --- Identifiants d'article -------------------------------------------------------


def test_normalisation_des_articles():
    assert normaliser_article("article 244 quater B du code général des impôts") == (
        "244 quater b cgi"
    )
    assert noyau_article("CGI, art. 244 quater B, II, k") == "244 quater b"
    assert noyau_article("article 238 bis, II") == "238 bis"
    assert noyau_article("article 44 sexies-0 A du CGI") != noyau_article("244 quater B")


# --- A3 : machine à états -----------------------------------------------------------


@pytest.mark.parametrize(
    ("actuel", "evenement", "attendu"),
    [
        (S.PROPOSEE, E.ADOPTION, S.VOTEE),
        (S.PROPOSEE, E.REJET, S.ABANDONNEE),
        (S.VOTEE, E.PUBLICATION, S.PUBLIEE),
        (S.VOTEE, E.CENSURE, S.ABANDONNEE),
        (S.PUBLIEE, E.ENTREE_EN_VIGUEUR, S.APPLIQUEE),
    ],
)
def test_transitions_autorisees(actuel, evenement, attendu):
    assert prochain_statut(actuel, evenement) == attendu


@pytest.mark.parametrize(
    ("actuel", "evenement"),
    [
        (S.PROPOSEE, E.PUBLICATION),  # le vote manque
        (S.PUBLIEE, E.DEPOT),  # pas de retour en arrière
        (S.APPLIQUEE, E.CENSURE),
        (S.ABANDONNEE, E.ADOPTION),
    ],
)
def test_transitions_interdites(actuel, evenement):
    with pytest.raises(TransitionInterdite):
        prochain_statut(actuel, evenement)


def test_evenement_qui_confirme_le_statut():
    assert prochain_statut(S.VOTEE, E.ADOPTION) is None


def test_statut_initial():
    assert statut_initial(E.DEPOT) == S.PROPOSEE
    assert statut_initial(E.PUBLICATION) == S.PUBLIEE  # décret publié directement
    with pytest.raises(TransitionInterdite):
        statut_initial(E.REJET)


# --- A5 : graduation (côté Python) ------------------------------------------------


@pytest.mark.parametrize(
    ("statut", "attendu"),
    [
        (S.PROPOSEE, Niveau.INFORMATION),
        (S.ABANDONNEE, Niveau.INFORMATION),
        (S.VOTEE, Niveau.ACTION),
        (S.PUBLIEE, Niveau.ACTION),
        (S.APPLIQUEE, Niveau.ACTION),
    ],
)
def test_niveau(statut, attendu):
    assert niveau(statut) == attendu


def test_action_interdite_sur_mesure_proposee():
    with pytest.raises(ActionInterdite):
        verifier_action_autorisee(S.PROPOSEE)
    verifier_action_autorisee(S.VOTEE)


def test_amendement_adopte_ne_change_jamais_le_statut():
    # Adopté en séance, le texte peut encore changer : pas d'action possible (A5).
    assert prochain_statut(S.PROPOSEE, E.ADOPTION_AMENDEMENT) is None
    assert prochain_statut(S.VOTEE, E.ADOPTION_AMENDEMENT) is None
    assert statut_initial(E.ADOPTION_AMENDEMENT) == S.PROPOSEE
