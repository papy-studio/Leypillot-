"""Outils de texte : normalisation, vérification mot pour mot, identifiants d'article, dates."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

_ESPACES = re.compile(r"\s+")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})

LONGUEUR_MIN_CITATION = 10


def normaliser(texte: str) -> str:
    """Espaces (dont insécables) et apostrophes uniformisés ; casse et accents conservés."""
    texte = unicodedata.normalize("NFKC", texte).translate(_APOSTROPHES)
    return _ESPACES.sub(" ", texte).strip()


def citation_verifiee(citation: str | None, texte: str) -> bool:
    """Vrai si la citation figure mot pour mot dans le texte (aux espaces près)."""
    if not citation:
        return False
    cherchee = normaliser(citation).strip(" «»\"'")
    return len(cherchee) >= LONGUEUR_MIN_CITATION and cherchee in normaliser(texte)


def sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


_CODES = (
    (re.compile(r"code general des impots"), "cgi"),
    (re.compile(r"livre des procedures fiscales"), "lpf"),
    (re.compile(r"code de la securite sociale"), "css"),
)
_MOTS_VIDES = {"article", "art", "du", "de", "la", "le", "l", "des", "au", "aux", "d", "et"}
_SUFFIXES = "bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|undecies|duodecies"
_ROMAINS = r"(?:i{1,3}|iv|vi{0,3}|ix|x)"
_NOYAU = re.compile(rf"\b(\d+(?:-\d+)?(?: (?:{_SUFFIXES}))?(?: (?!{_ROMAINS}\b)[a-z]{{1,2}}\b)?)")


def normaliser_article(texte: str) -> str:
    """« CGI, art. 244 quater B » et « article 244 quater B du code général des impôts »
    deviennent tous deux « cgi 244 quater b » (mots triés sans importance pour rapidfuzz)."""
    texte = sans_accents(normaliser(texte)).lower()
    for motif, abreviation in _CODES:
        texte = motif.sub(abreviation, texte)
    texte = re.sub(r"[^\w-]+", " ", texte)
    return " ".join(mot for mot in texte.split() if mot not in _MOTS_VIDES)


def noyau_article(texte: str) -> str | None:
    """Numéro d'article sans les subdivisions : « 244 quater b » pour « 244 quater B, II, k »."""
    trouve = _NOYAU.search(normaliser_article(texte))
    return trouve.group(1) if trouve else None


def normaliser_libelle(texte: str) -> str:
    texte = sans_accents(normaliser(texte)).lower()
    texte = re.sub(r"[^\w]+", " ", texte)
    return " ".join(mot for mot in texte.split() if mot not in _MOTS_VIDES)


MOIS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
_NOMS_MOIS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def date_en_francais(jour: date) -> str:
    numero = "1er" if jour.day == 1 else str(jour.day)
    return f"{numero} {_NOMS_MOIS[jour.month - 1]} {jour.year}"
