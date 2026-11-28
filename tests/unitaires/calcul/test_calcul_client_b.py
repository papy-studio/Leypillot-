"""Tests du moteur de calcul (lot 3) : fil rouge client B et bugs relevés en relecture."""

import json
from decimal import Decimal
from pathlib import Path

from leypilot.calcul import moteur
from leypilot.calcul.interface import MesureChiffrable
from leypilot.calcul.moteur import simuler_mesure
from leypilot.calcul.parametres import charger

FICHIER = Path(__file__).parents[3] / "donnees_exemple" / "lot3_client_b.json"
DONNEES = json.loads(FICHIER.read_text(encoding="utf-8"))
CLIENT = DONNEES["client"]
MESURE = MesureChiffrable(**DONNEES["mesure"])


def variante(**changements):
    """Une copie de la mesure du client B avec quelques champs changés (et revérifiés)."""
    return MesureChiffrable(**{**MESURE.model_dump(), **changements})


def simuler(entrees=None, mesure=MESURE, exercice=None):
    return simuler_mesure(
        CLIENT["client_id"],
        CLIENT["entrees"] if entrees is None else entrees,
        mesure,
        CLIENT["exercice"] if exercice is None else exercice,
    )


def test_client_b_ecart_40000():
    resultat = simuler()
    attendu = DONNEES["resultat_attendu"]
    assert resultat.statut == "ok"
    assert resultat.aide_loi_actuelle == Decimal(attendu["aide_loi_actuelle"])
    assert resultat.aide_reforme == Decimal(attendu["aide_reforme"])
    assert resultat.ecart == Decimal(attendu["ecart"])


def test_les_deux_traces_sont_gardees():
    resultat = simuler()
    assert resultat.trace_loi_actuelle[-1].valeur == Decimal("120000.00")
    assert resultat.trace_reforme[-1].valeur == Decimal("80000.00")
    assert resultat.trace_reforme[0].source == "profil client"


def test_bug1_mesure_sur_le_plafond():
    mesure = variante(
        parametre="plafond_depenses",
        ancienne_valeur=400000,
        nouvelle_valeur=300000,
    )
    resultat = simuler(mesure=mesure)
    assert resultat.aide_reforme == Decimal("90000.00")
    assert resultat.ecart == Decimal("30000.00")


def test_parametre_inconnu():
    resultat = simuler(mesure=variante(parametre="taux du CII"))
    assert resultat.statut == "impossible"
    assert "Paramètre inconnu" in resultat.motif


def test_bug2_cir_pas_encore_gere():
    resultat = simuler(mesure=variante(dispositif="CIR"))
    assert resultat.statut == "impossible"
    assert resultat.ecart is None


def test_bug3_grande_entreprise_sans_cii():
    resultat = simuler(entrees={"effectif": 5000, "depenses_innovation": 400000})
    assert resultat.aide_loi_actuelle == 0
    assert resultat.ecart == 0


def test_bug4_regle_deja_validee_dans_le_yaml(monkeypatch):
    regles = charger("CII")
    regles["taux"]["valeurs"]["2026-01-01"] = 0.20  # l'expert a validé la mesure
    monkeypatch.setattr(moteur, "charger", lambda dispositif: regles)
    resultat = simuler()
    assert resultat.ecart == Decimal("40000.00")


def test_bug5_empreinte_change_si_les_regles_changent(monkeypatch):
    avant = simuler().empreinte
    monkeypatch.setattr(moteur, "empreinte_regles", lambda dispositif: "autres regles")
    assert simuler().empreinte != avant


def test_meme_calcul_meme_empreinte():
    assert simuler().empreinte == simuler().empreinte


def test_bug6_date_effet_en_cours_d_exercice():
    resultat = simuler(mesure=variante(date_effet="2026-07-01"))
    assert resultat.statut == "en_attente"
    assert resultat.ecart is None


def test_date_estimee_donne_un_chiffrage_provisoire():
    resultat = simuler(mesure=variante(date_certaine=False))
    assert resultat.statut == "ok"
    assert resultat.provisoire is True


def test_profil_incomplet():
    resultat = simuler(entrees={"effectif": 40})
    assert resultat.statut == "impossible"
    assert resultat.champs_manquants == ["depenses_innovation"]


def test_avant_la_date_effet_pas_d_ecart():
    assert simuler(exercice=2025).ecart == 0
