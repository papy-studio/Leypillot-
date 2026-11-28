"""Lecture des paramètres YAML datés (lot 3, P3)."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

import openfisca_leypilot

DOSSIER_PARAMETRES = Path(openfisca_leypilot.__file__).parent / "parametres"


def chemin(dispositif: str) -> Path:
    """Fichier YAML d'un dispositif, par exemple « CII » -> cii.yaml."""
    return DOSSIER_PARAMETRES / f"{dispositif.lower()}.yaml"


def charger(dispositif: str) -> dict:
    """Lit tous les paramètres d'un dispositif."""
    with chemin(dispositif).open(encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)


def empreinte_regles(dispositif: str) -> str:
    """Empreinte du contenu du fichier de règles : elle change dès qu'une valeur change."""
    return hashlib.sha256(chemin(dispositif).read_bytes()).hexdigest()


def _serie(valeurs: dict) -> list[tuple[date, Decimal]]:
    """Transforme {"2023-01-01": 0.30} en [(date(2023, 1, 1), Decimal("0.3"))], triée."""
    return sorted(
        (date.fromisoformat(str(date_effet)), Decimal(str(valeur)))
        for date_effet, valeur in valeurs.items()
    )


def valeur_a_date(valeurs: dict, jour: date) -> Decimal:
    """Renvoie la valeur en vigueur au jour donné (dernière date d'effet <= jour)."""
    retenue = None
    for date_effet, valeur in _serie(valeurs):
        if date_effet <= jour:
            retenue = valeur
    if retenue is None:
        raise ValueError(f"Aucune valeur en vigueur le {jour}")
    return retenue


def valeurs_sans_mesure(valeurs: dict, date_effet: date) -> dict:
    """La loi sans la mesure : on retire la valeur datée du jour d'effet de la mesure,
    au cas où l'expert l'a déjà ajoutée au YAML."""
    return {d: v for d, v in valeurs.items() if date.fromisoformat(str(d)) != date_effet}


def valeurs_avec_mesure(valeurs: dict, date_effet: date, nouvelle_valeur: Decimal) -> dict:
    """La loi avec la mesure : la nouvelle valeur s'applique à partir de sa date d'effet."""
    return {**valeurs_sans_mesure(valeurs, date_effet), date_effet.isoformat(): nouvelle_valeur}
