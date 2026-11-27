"""Lecture des paramètres YAML datés (lot 3, P3)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

import openfisca_leypilot

DOSSIER_PARAMETRES = Path(openfisca_leypilot.__file__).parent / "parametres"


def charger(dispositif: str) -> dict:
    """Lit le fichier YAML d'un dispositif, par exemple « CII » -> cii.yaml."""
    chemin = DOSSIER_PARAMETRES / f"{dispositif.lower()}.yaml"
    with chemin.open(encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)


def valeur_a_date(parametre: dict, jour: date) -> float:
    """Renvoie la valeur en vigueur au jour donné (dernière date d'effet <= jour)."""
    retenue = None
    for date_effet, valeur in sorted(parametre["valeurs"].items()):
        if date.fromisoformat(str(date_effet)) <= jour:
            retenue = valeur
    if retenue is None:
        raise ValueError(f"Aucune valeur en vigueur le {jour}")
    return retenue