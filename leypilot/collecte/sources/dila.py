"""Outils communs aux fichiers XML de la DILA (fonds JORF et LEGI)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime

from leypilot.collecte.textes import texte_brut


def local(balise: str) -> str:
    return balise.rsplit("}", 1)[-1]


def premier(racine: ET.Element, nom: str) -> str | None:
    """Texte du premier élément ``nom`` (espaces de noms ignorés)."""
    for element in racine.iter():
        if local(element.tag) == nom and (element.text or "").strip():
            return element.text.strip()  # type: ignore[union-attr]
    return None


def contenu_html(element: ET.Element | None) -> str:
    if element is None:
        return ""
    interieur = (element.text or "") + "".join(
        ET.tostring(enfant, encoding="unicode") for enfant in element
    )
    return texte_brut(interieur)


def jour(valeur: str | None) -> date | None:
    if not valeur or valeur.startswith("2999"):
        return None
    try:
        return date.fromisoformat(valeur[:10])
    except ValueError:
        return None


def entier(valeur: str | None) -> int | None:
    return int(valeur) if valeur and valeur.strip().isdigit() else None


def archives_publiees(page_html: str, depuis: date, fonds: str = "JORF") -> list[str]:
    """Noms des archives d'un fonds (JORF, LEGI) listées dans la page de la DILA,
    publiées depuis ``depuis``."""
    motif = re.compile(rf"{fonds}_(\d{{8}})-(\d{{6}})\.tar\.gz")
    return [
        f"{fonds}_{j}-{heure}.tar.gz"
        for j, heure in sorted(set(motif.findall(page_html)))
        if datetime.strptime(j, "%Y%m%d").date() >= depuis
    ]
