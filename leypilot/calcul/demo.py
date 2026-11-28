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
    for titre, trace in (
        ("Loi actuelle", resultat.trace_loi_actuelle),
        ("Avec la réforme", resultat.trace_reforme),
    ):
        print(titre)
        for etape in trace:
            print(f"  - {etape.libelle} : {etape.valeur:,}")
    print(f"Écart : {resultat.ecart:,} EUR")


if __name__ == "__main__":
    main()
