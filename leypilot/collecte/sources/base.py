"""Interface commune des connecteurs (S1) et format d'un document collecté."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import httpx

from leypilot.collecte.completude import Rapport
from leypilot.collecte.textes import empreinte_etat, empreinte_texte

AGENT = "Leypilot/0.1 (projet étudiant, École Centrale Casablanca)"


class Source(StrEnum):
    JORF = "JORF"  # Journal officiel (fichiers DILA)
    LEGI = "LEGI"  # codes consolidés (fichiers DILA ou API PISTE)
    AN = "AN"  # Assemblée nationale
    SENAT = "SENAT"
    BOFIP = "BOFIP"


class TypeTexte(StrEnum):
    """Mêmes valeurs que ``leypilot.mesure.entree.TypeTexte`` (lot 2)."""

    PROJET_LOI = "projet_loi"
    PROPOSITION_LOI = "proposition_loi"
    AMENDEMENT = "amendement"
    TEXTE_ADOPTE = "texte_adopte"
    LOI = "loi"
    ORDONNANCE = "ordonnance"
    DECRET = "decret"
    ARRETE = "arrete"
    DOCTRINE = "doctrine"
    VERSION_CONSOLIDEE = "version_consolidee"  # LEGI : pas encore prévu par le lot 2


@dataclass
class DocumentBrut:
    """Un texte reçu d'une source, déjà normalisé, avant enregistrement en base."""

    source: Source
    identifiant: str  # JORFTEXT…, UID d'amendement, n° Sénat, identifiant BOFiP
    nature: str  # valeur brute de la source (LOI, DECRET, AMENDEMENT…)
    type_texte: TypeTexte
    titre: str | None
    date_document: date | None
    url_officielle: str
    texte: str  # normalisé (voir textes.normaliser)
    etat: dict[str, Any] = field(default_factory=dict)  # sort, état, dates : empreinte_etat
    meta: dict[str, Any] = field(default_factory=dict)
    nor: str | None = None
    eli: str | None = None
    dossier_legislatif: str | None = None
    numero_amendement: str | None = None
    etape: str | None = None  # étape explicite pour le lot 2 (adoption, rejet…), sinon déduite
    chemin_brut: str = ""

    @property
    def empreinte_texte(self) -> str:
        return empreinte_texte(self.texte)

    @property
    def empreinte_etat(self) -> str:
        return empreinte_etat(self.etat)


@dataclass
class Collecte:
    """Résultat d'un passage de connecteur : documents du périmètre et contrôle."""

    source: Source
    fichier: str | None
    documents: list[DocumentBrut]
    controle: Rapport
    nb_lus: int = 0  # documents lus avant le filtre de périmètre


class Connecteur(Protocol):
    """Interface imposée par la répartition : ``recuperer(depuis)``."""

    source: Source

    def recuperer(self, depuis: date) -> Iterator[Collecte]:
        """Une ``Collecte`` par fichier ou par lot publié depuis la date donnée."""
        ...


def client_http(timeout: float = 120) -> httpx.Client:
    return httpx.Client(headers={"User-Agent": AGENT}, timeout=timeout, follow_redirects=True)


def telecharger(client: httpx.Client, url: str, destination: Path) -> Path:
    """Télécharge en flux vers ``destination`` (fichier brut conservé tel quel)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partiel = destination.with_suffix(destination.suffix + ".partiel")
    with client.stream("GET", url) as reponse:
        reponse.raise_for_status()
        with partiel.open("wb") as fichier:
            for bloc in reponse.iter_bytes(1 << 20):
                fichier.write(bloc)
    partiel.replace(destination)
    return destination


# Sort d'un amendement (AN et Sénat) -> étape transmise au lot 2. Tout amendement qui ne
# sera pas dans le texte (rejeté, tombé, retiré, non soutenu, irrecevable) devient « rejet » :
# la mesure qu'il portait est abandonnée. Le sort brut reste dans ``etat`` et ``meta``.
# Proposition à valider avec la personne 2.
_SORTS_ADOPTION = ("adopt",)
_SORTS_REJET = ("rejet", "tomb", "retir", "non soutenu", "irrecevable", "non retenu")


def etape_depuis_sort(sort: str | None) -> str | None:
    if not sort:
        return None
    sort = sort.strip().lower()
    if sort.startswith(_SORTS_ADOPTION):
        return "adoption"
    if any(mot in sort for mot in _SORTS_REJET):
        return "rejet"
    return None
