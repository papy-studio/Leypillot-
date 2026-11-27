"""A1 · Contrôle de complétude : prouver qu'il ne manque aucun texte.

Chaque source fournit une référence à laquelle comparer ce qu'on a reçu :

- JO : le sommaire du numéro (JORFCONT) liste tous ses textes, et les numéros de
  séquence (NUM_SEQUENCE) se suivent de 1 à n ;
- Assemblée nationale et Sénat : les numéros d'amendement d'un même texte se suivent ;
- BOFiP : les archives hebdomadaires sont numérotées sans trou (flux 44, 45, 46…).

Un écart ne bloque pas la collecte : il est enregistré dans ``execution_collecte`` avec
le statut « ecart », et l'administrateur reçoit une alerte technique dans l'application.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


def trous(numeros: Iterable[int]) -> list[int]:
    """Numéros manquants entre le plus petit et le plus grand numéro reçu."""
    tries = sorted(set(numeros))
    if not tries:
        return []
    return sorted(set(range(tries[0], tries[-1] + 1)) - set(tries))


@dataclass
class Rapport:
    """Résultat d'un contrôle : ``complet`` vrai si aucun écart."""

    attendus: int
    recus: int
    ecarts: list[str] = field(default_factory=list)

    @property
    def complet(self) -> bool:
        return not self.ecarts


def controler_sommaire(
    annonces: Iterable[str], recus: Iterable[str], sequences: Iterable[int] = ()
) -> Rapport:
    """Compare les identifiants annoncés par un sommaire à ceux reçus.

    ``sequences`` (facultatif) : numéros d'ordre des textes reçus, qui doivent se suivre
    à partir de 1.
    """
    annonces, recus = list(dict.fromkeys(annonces)), set(recus)
    sequences = sorted(set(sequences))
    ecarts = [f"absent de l'archive : {ident}" for ident in annonces if ident not in recus]
    ecarts += [f"hors sommaire : {ident}" for ident in sorted(recus - set(annonces))]
    if sequences:
        manquants = trous([1, *sequences]) if sequences[0] != 1 else trous(sequences)
        ecarts += [f"séquence manquante : {n}" for n in manquants]
    return Rapport(attendus=len(annonces), recus=len(recus), ecarts=ecarts)


def controler_numeros(numeros: Iterable[int], libelle: str = "numéro") -> Rapport:
    """Contrôle d'une suite numérotée (amendements, flux BOFiP)."""
    numeros = list(numeros)
    manquants = trous(numeros)
    attendus = (max(numeros) - min(numeros) + 1) if numeros else 0
    return Rapport(
        attendus=attendus,
        recus=len(set(numeros)),
        ecarts=[f"{libelle} manquant : {n}" for n in manquants],
    )
