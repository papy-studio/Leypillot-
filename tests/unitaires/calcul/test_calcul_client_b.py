"""Tests du moteur de calcul (lot 3) sur le fil rouge client B."""

import json
from pathlib import Path

from leypilot.calcul.interface import MesureChiffrable
from leypilot.calcul.moteur import simuler_mesure

FICHIER = Path(__file__).parents[3] / "donnees_exemple" / "lot3_client_b.json"
DONNEES = json.loads(FICHIER.read_text(encoding="utf-8"))
CLIENT = DONNEES["client"]
MESURE = MesureChiffrable(**DONNEES["mesure"])


def test_client_b_ecart_40000():
    resultat = simuler_mesure(CLIENT["client_id"], CLIENT["entrees"], MESURE, CLIENT["exercice"])
    assert resultat.statut == "ok"
    assert resultat.aide_loi_actuelle == 120000
    assert resultat.aide_reforme == 80000
    assert resultat.ecart == 40000


def test_meme_calcul_meme_empreinte():
    premier = simuler_mesure(CLIENT["client_id"], CLIENT["entrees"], MESURE, CLIENT["exercice"])
    second = simuler_mesure(CLIENT["client_id"], CLIENT["entrees"], MESURE, CLIENT["exercice"])
    assert premier.empreinte == second.empreinte
    assert premier.ecart == second.ecart


def test_profil_incomplet():
    resultat = simuler_mesure(CLIENT["client_id"], {"effectif": 40}, MESURE, CLIENT["exercice"])
    assert resultat.statut == "impossible"
    assert resultat.ecart is None
    assert resultat.champs_manquants == ["depenses_innovation"]


def test_avant_la_date_effet_pas_d_ecart():
    resultat = simuler_mesure(CLIENT["client_id"], CLIENT["entrees"], MESURE, 2025)
    assert resultat.ecart == 0