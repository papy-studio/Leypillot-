"""Connecteur Assemblée nationale : amendements (open data, archive JSON zippée).

Adresse : https://data.assemblee-nationale.fr (législature 17, « amendements_div_legis »).
Un fichier JSON par amendement. Les six derniers chiffres de l'UID sont le numéro
d'ordre de dépôt : un trou dans ces numéros signale un amendement manquant.
"""

from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from leypilot.collecte.cibles import dans_perimetre
from leypilot.collecte.completude import Rapport, controler_numeros
from leypilot.collecte.sources.base import (
    Collecte,
    DocumentBrut,
    Source,
    TypeTexte,
    client_http,
    etape_depuis_sort,
    telecharger,
)
from leypilot.collecte.textes import normaliser, texte_brut

URL_AMENDEMENTS = (
    "https://data.assemblee-nationale.fr/static/openData/repository/17/loi/"
    "amendements_div_legis/Amendements.json.zip"
)
URL_AMENDEMENT = "https://www.assemblee-nationale.fr/dyn/opendata/{}.json"


def _date(valeur: str | None) -> date | None:
    try:
        return date.fromisoformat(valeur[:10]) if valeur else None
    except ValueError:
        return None


def document_amendement(donnees: dict[str, Any]) -> DocumentBrut:
    """Un amendement au format de la source vers un ``DocumentBrut`` (sans filtre)."""
    amendement = donnees.get("amendement", donnees)  # l'enveloppe varie selon les exports
    ident = amendement.get("identification") or {}
    corps = (amendement.get("corps") or {}).get("contenuAuteur") or {}
    vie = amendement.get("cycleDeVie") or {}
    division = (amendement.get("pointeurFragmentTexte") or {}).get("division") or {}
    sort = vie.get("sort")
    if isinstance(sort, dict):  # certains exports donnent {"libelle": …}
        sort = sort.get("libelle") or sort.get("sortEnSeance")
    dispositif = texte_brut(corps.get("dispositif"))
    expose = texte_brut(corps.get("exposeSommaire"))
    uid = amendement.get("uid", "")
    numero = ident.get("numeroLong") or ident.get("numeroOrdreDepot")
    return DocumentBrut(
        source=Source.AN,
        identifiant=uid,
        nature="AMENDEMENT",
        type_texte=TypeTexte.AMENDEMENT,
        titre=f"Amendement n° {numero}" if numero else None,
        date_document=_date(vie.get("dateDepot")),
        url_officielle=URL_AMENDEMENT.format(uid),
        texte=normaliser(f"{dispositif}\nExposé sommaire :\n{expose}" if expose else dispositif),
        etat={
            "sort": sort,
            "etat": vie.get("etatDesTraitements"),
            "date_sort": vie.get("dateSort"),
        },
        meta={
            "texte_legislatif": amendement.get("texteLegislatifRef"),
            "organe": ident.get("prefixeOrganeExamen"),
            "numero_ordre": ident.get("numeroOrdreDepot"),
            "article": division.get("articleDesignation"),
        },
        numero_amendement=str(numero) if numero else None,
        etape=etape_depuis_sort(sort),
    )


def lire_archive(chemin: Path, depuis: date | None = None) -> Collecte:
    documents, numeros = [], defaultdict(list)
    lus = 0
    with zipfile.ZipFile(chemin) as archive:
        for nom in archive.namelist():
            if not nom.endswith(".json"):
                continue
            document = document_amendement(json.loads(archive.read(nom)))
            lus += 1
            ordre = str(document.meta.get("numero_ordre") or "")
            texte_ref = document.meta.get("texte_legislatif")
            if texte_ref and ordre.isdigit():
                numeros[(texte_ref, document.meta.get("organe"))].append(int(ordre))
            if depuis and document.date_document and document.date_document < depuis:
                continue
            if dans_perimetre(document.texte):
                document.chemin_brut = f"{chemin.name}#{nom}"
                documents.append(document)

    # Contrôle limité aux textes qui portent au moins un amendement du périmètre.
    textes_suivis = {d.meta.get("texte_legislatif") for d in documents}
    ecarts, attendus, recus = [], 0, 0
    for (texte_ref, organe), liste in sorted(numeros.items(), key=lambda x: str(x[0])):
        if texte_ref not in textes_suivis:
            continue
        rapport = controler_numeros(liste, "amendement")
        attendus, recus = attendus + rapport.attendus, recus + rapport.recus
        ecarts += [f"{texte_ref} [{organe}] : {e}" for e in rapport.ecarts]
    return Collecte(
        source=Source.AN,
        fichier=chemin.name,
        documents=documents,
        controle=Rapport(attendus=attendus, recus=recus, ecarts=ecarts),
        nb_lus=lus,
    )


class ConnecteurAN:
    source = Source.AN

    def __init__(self, dossier_brut: Path, url: str = URL_AMENDEMENTS) -> None:
        self.dossier = dossier_brut / "an"
        self.url = url

    def recuperer(self, depuis: date) -> Iterator[Collecte]:
        with client_http(timeout=600) as client:
            chemin = telecharger(
                client, self.url, self.dossier / f"Amendements_{date.today():%Y%m%d}.json.zip"
            )
        yield lire_archive(chemin, depuis)
