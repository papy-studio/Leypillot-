"""Connecteur BOFiP : doctrine fiscale (archives hebdomadaires ``.tgz``).

La liste des archives vient de l'API de data.economie.gouv.fr (jeu « bofip-impots »).
Chaque archive (« flux ») a un numéro d'ordre lu dans son lien de téléchargement
(``…/opendata/flux/47``) et une empreinte MD5.

Règles de complétude :
- on se fie au numéro de flux, pas aux dates du nom de fichier (certaines archives
  portent une année erronée) ;
- seules les 7 dernières archives sont listées : un trou dans les numéros, ou un dernier
  flux de plus de 14 jours, déclenche une alerte technique.
"""

from __future__ import annotations

import hashlib
import re
import tarfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from leypilot.collecte.completude import Rapport, controler_numeros
from leypilot.collecte.sources.base import (
    Collecte,
    DocumentBrut,
    Source,
    TypeTexte,
    client_http,
    telecharger,
)
from leypilot.collecte.textes import texte_brut

URL_API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/bofip-impots/records"
URL_BOFIP = "https://bofip.impots.gouv.fr/bofip/{}"

# Séries de doctrine suivies (préfixes d'identifiant juridique).
SERIES = (
    "BOI-BIC-RICI-10-10",  # CIR, y compris le CII
    "BOI-BIC-CHAMP-80-20-20",  # JEI et JEU
)
AGE_MAX_JOURS = 14  # une semaine couverte + délai de mise en ligne


def numero_flux(enregistrement: dict[str, Any]) -> int:
    """Numéro d'ordre du flux, lu dans le lien de téléchargement (…/opendata/flux/47)."""
    return int(str(enregistrement["telechargement"]).rstrip("/").rsplit("/", 1)[-1])


def lister_flux(client: httpx.Client) -> list[dict[str, Any]]:
    reponse = client.get(URL_API, params={"limit": 100, "where": 'type="flux"'})
    reponse.raise_for_status()
    return sorted(reponse.json()["results"], key=numero_flux)


def controler_liste(flux: list[dict[str, Any]], aujourd_hui: date) -> Rapport:
    rapport = controler_numeros([numero_flux(f) for f in flux], "flux BOFiP")
    if flux:
        fin = date.fromisoformat(str(flux[-1]["date_de_fin"])[:10])
        if (age := (aujourd_hui - fin).days) > AGE_MAX_JOURS:
            rapport.ecarts.append(f"dernier flux terminé le {fin}, il y a {age} jours")
    else:
        rapport.ecarts.append("aucun flux listé")
    return rapport


def md5_attendu(client: httpx.Client, url: str) -> str | None:
    reponse = client.get(url)
    reponse.raise_for_status()
    trouve = re.search(r"\b[0-9a-fA-F]{32}\b", reponse.text)
    return trouve.group(0).lower() if trouve else None


def _champ(racine: ET.Element, nom: str) -> str | None:
    for element in racine.iter():
        if element.tag.rsplit("}", 1)[-1] == nom and (element.text or "").strip():
            return element.text.strip()  # type: ignore[union-attr]
    return None


def lire_archive(chemin: Path) -> Collecte:
    """Documents des séries suivies, lus en mémoire (rien n'est extrait sur le disque)."""
    documents, lus = [], 0
    with tarfile.open(chemin, "r:gz") as archive:
        membres = {m.name: m for m in archive.getmembers() if m.isfile()}
        for nom, membre in membres.items():
            if not nom.endswith("document.xml"):
                continue
            lus += 1
            fichier = archive.extractfile(membre)
            if fichier is None:
                continue
            racine = ET.fromstring(fichier.read())
            identifiant = _champ(racine, "identifier") or ""
            if not identifiant.startswith(SERIES):
                continue
            dossier = nom.rsplit("/", 1)[0]
            corps = next((membres[n] for n in membres if n.startswith(dossier + "/data.")), None)
            lu = archive.extractfile(corps) if corps else None
            texte = lu.read().decode("utf-8", "replace") if lu else ""
            jour = _champ(racine, "date")
            documents.append(
                DocumentBrut(
                    source=Source.BOFIP,
                    identifiant=identifiant,
                    nature="DOCTRINE",
                    type_texte=TypeTexte.DOCTRINE,
                    titre=_champ(racine, "title"),
                    date_document=date.fromisoformat(jour[:10]) if jour else None,
                    url_officielle=URL_BOFIP.format(identifiant),
                    texte=texte_brut(texte),
                    etat={"date": jour},
                    meta={"contenu_id": _champ(racine, "contenu_id"), "dossier": dossier},
                    chemin_brut=f"{chemin.name}#{dossier}",
                )
            )
    return Collecte(
        source=Source.BOFIP,
        fichier=chemin.name,
        documents=documents,
        controle=Rapport(attendus=0, recus=0),
        nb_lus=lus,
    )


class ArchiveCorrompue(ValueError):
    pass


class ConnecteurBOFiP:
    source = Source.BOFIP

    def __init__(self, dossier_brut: Path) -> None:
        self.dossier = dossier_brut / "bofip"

    def recuperer(self, depuis: date) -> Iterator[Collecte]:
        with client_http() as client:
            flux = lister_flux(client)
            controle_liste = controler_liste(flux, date.today())
            for enregistrement in flux:
                if date.fromisoformat(str(enregistrement["date_de_fin"])[:10]) < depuis:
                    continue
                chemin = self.dossier / str(enregistrement["nom_du_fichier"])
                if not chemin.exists():
                    telecharger(client, str(enregistrement["telechargement"]), chemin)
                attendu = md5_attendu(client, str(enregistrement["empreinte"]))
                obtenu = hashlib.md5(chemin.read_bytes()).hexdigest()
                if attendu and attendu != obtenu:
                    chemin.unlink()
                    raise ArchiveCorrompue(
                        f"{chemin.name} : MD5 {obtenu} au lieu de {attendu}, archive rejetée"
                    )
                collecte = lire_archive(chemin)
                collecte.controle = controle_liste
                yield collecte
