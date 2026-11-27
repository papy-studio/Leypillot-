"""Démo du fil rouge client B : python -m leypilot.calcul.demo"""

import json
from pathlib import Path

from leypilot.calcul.interface import MesureChiffrable
from leypilot.calcul.moteur import simuler_mesure

FICHIER = Path(__file__).parents[2] / "donnees_exemple" / "lot3_client_b.json"


def main() -> None:
    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    client = donnees["client"]
    mesure = MesureChiffrable(**donnees["mesure"])
    resultat = simuler_mesure(client["client_id"], client["entrees"], mesure, client["exercice"])
    print(f"Client : {client['nom']}  |  statut : {resultat.statut}")
    for etape in resultat.trace:
        print(f"  - {etape.libelle} : {etape.valeur:,.2f}")
    print(f"Écart : {resultat.ecart:,.2f} EUR")


if __name__ == "__main__":
    main()