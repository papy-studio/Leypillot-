"""Contexte du résumé S3, retrouvé par identifiant (pas de base vectorielle).

Le corpus utile est minuscule : quelques articles du CGI et les sections du
BOFiP sur le CIR, le CII et la JEI. ``SourceContexte`` est l'interface ;
l'implémentation en base lira les documents collectés par le lot 1.
"""

from __future__ import annotations

from typing import Protocol

from leypilot.mesure.schemas import Changement, Dispositif
from leypilot.mesure.textes import noyau_article

LONGUEUR_MAX_CONTEXTE = 6000


class SourceContexte(Protocol):
    def texte_article(self, article: str) -> str | None: ...

    def doctrine(self, dispositif: Dispositif) -> str | None: ...


class ContexteVide:
    def texte_article(self, article: str) -> str | None:
        return None

    def doctrine(self, dispositif: Dispositif) -> str | None:
        return None


class ContexteMemoire:
    """Contexte en mémoire, indexé par numéro d'article (« 244 quater b »)."""

    def __init__(
        self,
        articles: dict[str, str] | None = None,
        doctrine: dict[Dispositif, str] | None = None,
    ) -> None:
        self._articles = {
            noyau_article(cle) or cle: texte for cle, texte in (articles or {}).items()
        }
        self._doctrine = dict(doctrine or {})

    def texte_article(self, article: str) -> str | None:
        return self._articles.get(noyau_article(article) or article)

    def doctrine(self, dispositif: Dispositif) -> str | None:
        return self._doctrine.get(dispositif)


def construire_contexte(
    source: SourceContexte, changement: Changement, longueur_max: int = LONGUEUR_MAX_CONTEXTE
) -> str:
    morceaux = []
    if article := source.texte_article(changement.article_vise):
        morceaux.append(f"Article en vigueur ({changement.article_vise}) :\n{article}")
    if doctrine := source.doctrine(changement.dispositif):
        morceaux.append(f"Doctrine BOFiP ({changement.dispositif}) :\n{doctrine}")
    contexte = "\n\n".join(morceaux) or "Aucun contexte disponible."
    return contexte[:longueur_max]
