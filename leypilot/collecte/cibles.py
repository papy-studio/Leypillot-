"""Périmètre de la veille : filtre large des documents et table cible des articles.

Deux niveaux de filtre :

1. ``dans_perimetre`` (niveau document) : volontairement large. Un doute fait entrer
   le texte, parce qu'un texte manqué ne se rattrape plus ensuite.
2. ``rattacher`` (niveau changement) : précis. Un changement n'est rattaché à un
   dispositif que s'il touche un article (ou une subdivision) de la table cible.

Le contenu de ``CIBLES_ARTICLES`` est la version initiale de la table ``cible`` :
``charger_cibles`` la recopie en base au premier démarrage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CGI = "code général des impôts"
LPF = "livre des procédures fiscales"
LOI_JEI = "loi n° 2003-1311"

# Mots-clés du filtre large. Un sigle seul ne suffit pas toujours (dans la loi de
# finances pour 2025, « CIR » désigne aussi le contrat d'intégration républicaine),
# mais au niveau document on préfère un faux positif à un texte manqué.
MOTS_CLES = re.compile(
    r"244\s*quater\s*b"
    r"|44\s*sexies(?:-0)?\s*a"
    r"|1383\s*d|1466\s*d"
    r"|cr[ée]dit d'imp[ôo]t (?:en faveur de la )?recherche"
    r"|cr[ée]dit d'imp[ôo]t innovation"
    r"|jeunes? entreprises? (?:universitaires?|innovantes?|d'innovation|de croissance)"
    r"|\b(?:cir|cii|jei|jeu)\b",
    re.IGNORECASE,
)


def dans_perimetre(*champs: str | None) -> bool:
    """Vrai si l'un des champs (titre, dispositif, exposé, texte) évoque le périmètre."""
    return bool(MOTS_CLES.search(" ".join(c for c in champs if c).replace("’", "'")))


@dataclass(frozen=True)
class CibleArticle:
    dispositifs: tuple[str, ...]
    niveau: str  # « coeur » : porte le dispositif ; « connexe » : le modifie de l'extérieur


CIBLES_ARTICLES: dict[tuple[str, str], CibleArticle] = {
    (CGI, "244 quater B"): CibleArticle(("CIR",), "coeur"),
    (CGI, "44 sexies-0 A"): CibleArticle(("JEI",), "coeur"),
    (CGI, "44 sexies A"): CibleArticle(("JEI",), "coeur"),
    (CGI, "1383 D"): CibleArticle(("JEI",), "connexe"),
    (CGI, "1466 D"): CibleArticle(("JEI",), "connexe"),
    (LPF, "L. 80 B"): CibleArticle(("CIR", "JEI"), "connexe"),
    (LOI_JEI, "13"): CibleArticle(("JEI",), "connexe"),
    (LOI_JEI, "131"): CibleArticle(("JEI",), "connexe"),
}

# Subdivisions d'un article qui portent un autre dispositif que l'article entier.
# Le CII vit dans l'article du CIR : son taux est dans la quatrième phrase du premier
# alinéa du I, ses dépenses au k du II.
CIBLES_SUBDIVISIONS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("244 quater B", re.compile(r"\bk du II\b"), "CII"),
    ("244 quater B", re.compile(r"quatrième phrase (?:du premier alinéa )?du I\b"), "CII"),
)


def rattacher(articles: list[tuple[str | None, str]], localisation: str, passage: str) -> list[str]:
    """Dispositifs touchés par une opération, dans l'ordre, sans doublon."""
    resultat: list[str] = []
    zone = f"{localisation} {passage}"
    for cle in articles:
        cible = CIBLES_ARTICLES.get(cle)  # type: ignore[arg-type]
        if cible is None:
            continue
        regle = [d for art, motif, d in CIBLES_SUBDIVISIONS if art == cle[1] and motif.search(zone)]
        for dispositif in regle[:1] or cible.dispositifs:
            if dispositif not in resultat:
                resultat.append(dispositif)
    return resultat


def est_cible(code: str | None, article: str | None) -> bool:
    return (code, article) in CIBLES_ARTICLES  # type: ignore[comparison-overlap]
