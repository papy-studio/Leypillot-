"""Normalisation des textes et empreintes SHA-256 (S1).

Une seule règle de normalisation sert partout dans le lot 1 : au stockage du texte
(``document.texte``), au calcul de l'empreinte et à la vérification mot pour mot.
Le texte normalisé garde ses retours à la ligne : l'extraction lit ligne par ligne.

Conséquence pour le lot 2 : ``Changement.texte_source`` reçoit ``document.texte``,
donc ``sha256(texte_source)`` côté lot 2 vaut exactement ``document.empreinte_texte``.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from typing import Any

# Espaces insécables et fines (U+00A0, U+202F, U+2007, U+2009) ramenées à l'espace simple.
_ESPACES_SPECIALES = re.compile("[    ]")
_ESPACES_LIGNE = re.compile(r"[ \t]+")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def normaliser(texte: str) -> str:
    """NFC, espaces unifiées, apostrophes droites, « İ » ramené à « I ».

    Le « I » à point suscrit (U+0130) a été vu dans un texte adopté publié par le Sénat
    (« İI. – ») : sans cette règle, la numérotation « II » n'est pas reconnue.
    """
    texte = unicodedata.normalize("NFC", texte)
    texte = _ESPACES_SPECIALES.sub(" ", texte).translate(_APOSTROPHES).replace("İ", "I")
    lignes = (_ESPACES_LIGNE.sub(" ", ligne).strip() for ligne in texte.splitlines())
    return "\n".join(ligne for ligne in lignes if ligne)


_BALISES_LIGNE = re.compile(r"<\s*(?:br\s*/?|/p|/div|/li|/tr|/h\d)\s*>", re.IGNORECASE)
_BALISES = re.compile(r"<[^>]+>")


def texte_brut(fragment: str | None) -> str:
    """HTML vers texte : les fins de paragraphe deviennent des retours à la ligne."""
    if not fragment:
        return ""
    texte = _BALISES_LIGNE.sub("\n", fragment)
    texte = html.unescape(_BALISES.sub(" ", texte))
    return normaliser(texte)


def sha256(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def empreinte_texte(texte_normalise: str) -> str:
    """Empreinte du texte normalisé : change seulement si le contenu change."""
    return sha256(texte_normalise)


def empreinte_etat(etat: dict[str, Any]) -> str:
    """Empreinte de l'état d'un texte (sort, état, dates) : change quand le texte avance
    dans la procédure sans que son contenu change (amendement adopté, article abrogé)."""
    return sha256(json.dumps(etat, ensure_ascii=False, sort_keys=True, default=str))
