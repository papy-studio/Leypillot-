"""Filtre anti-montant : le LLM ne produit jamais un montant.

Utilisé par S3 (un montant du résumé doit figurer dans la citation) et
réutilisable par G4 (aucun chiffre en dur hors des emplacements ``{...}``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_SEPARATEUR = r"[   .]"
_NOMBRE = rf"\d{{1,3}}(?:{_SEPARATEUR}\d{{3}})+(?:,\d+)?|\d+(?:,\d+)?"
_MULTIPLICATEUR = r"milliards?|millions?|mille|Mds?|Md|M|k"
_UNITE = r"€|euros?\b|EUR\b"

_MONTANT = re.compile(
    rf"(?<![\d,.])(?P<nombre>{_NOMBRE})\s*"
    rf"(?:(?P<mult>{_MULTIPLICATEUR})\s*(?:d['’]\s*)?)?"
    rf"(?P<unite>{_UNITE})",
    re.IGNORECASE,
)
_FACTEURS = {
    "k": Decimal(10) ** 3,
    "mille": Decimal(10) ** 3,
    "m": Decimal(10) ** 6,
    "million": Decimal(10) ** 6,
    "millions": Decimal(10) ** 6,
    "md": Decimal(10) ** 9,
    "mds": Decimal(10) ** 9,
    "milliard": Decimal(10) ** 9,
    "milliards": Decimal(10) ** 9,
}
_EMPLACEMENT = re.compile(r"\{[^{}]*\}")
_CHIFFRE = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class Montant:
    brut: str
    valeur: Decimal


def _valeur(nombre: str, multiplicateur: str | None) -> Decimal | None:
    chiffres = re.sub(_SEPARATEUR, "", nombre).replace(",", ".")
    try:
        valeur = Decimal(chiffres)
    except InvalidOperation:
        return None
    if multiplicateur:
        valeur *= _FACTEURS.get(multiplicateur.lower(), Decimal(1))
    return valeur.normalize()


def extraire_montants(texte: str) -> list[Montant]:
    montants = []
    for trouve in _MONTANT.finditer(texte):
        valeur = _valeur(trouve["nombre"], trouve["mult"])
        if valeur is not None:
            montants.append(Montant(brut=trouve.group(0), valeur=valeur))
    return montants


def contient_montant(texte: str) -> bool:
    return bool(extraire_montants(texte))


def montants_non_justifies(sortie: str, reference: str) -> list[Montant]:
    """Montants de ``sortie`` absents de ``reference`` (comparés en valeur : 400 000 € = 400 k€)."""
    autorises = {m.valeur for m in extraire_montants(reference)}
    return [m for m in extraire_montants(sortie) if m.valeur not in autorises]


def chiffres_en_dur(texte: str) -> list[str]:
    """Chiffres écrits hors des emplacements ``{montant}``, ``{délai}``… (règle G4)."""
    return _CHIFFRE.findall(_EMPLACEMENT.sub("", texte))
