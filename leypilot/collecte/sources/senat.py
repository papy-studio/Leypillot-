"""Connecteur Sénat : amendements d'un texte (fichier CSV « jeu complet »).

Adresse : https://www.senat.fr/amendements/{session}/{texte}/jeu_complet_{session}_{texte}.csv

Particularités du fichier : encodage cp1252, séparateur tabulation, première ligne
``sep=``, noms de colonnes suivis d'espaces. Les numéros d'amendement d'une même partie
(« I-12 », « II-3 ») se suivent : un trou signale un amendement manquant.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

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

NUMERO = re.compile(r"^\s*(?:(?P<partie>[IVX]+)-)?(?P<n>\d+)")


def url_jeu_complet(session: str, texte: str | int, commission: bool = False) -> str:
    if commission:
        return (
            f"https://www.senat.fr/amendements/commissions/{session}/{texte}/"
            f"jeu_complet_commission_{session}_{texte}.csv"
        )
    return f"https://www.senat.fr/amendements/{session}/{texte}/jeu_complet_{session}_{texte}.csv"


def _date(valeur: str | None) -> date | None:
    valeur = (valeur or "").strip()
    for forme in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valeur[:10], forme).date()
        except ValueError:
            continue
    return None


def lignes_csv(contenu: bytes) -> list[dict[str, str]]:
    brut = contenu.decode("cp1252")
    lignes = brut.splitlines()
    if lignes and lignes[0].lower().startswith("sep="):
        lignes = lignes[1:]
    lecteur = csv.DictReader(io.StringIO("\n".join(lignes)), delimiter="\t")
    if lecteur.fieldnames is None:
        return []
    lecteur.fieldnames = [c.strip().lstrip("﻿") for c in lecteur.fieldnames]
    return [{k: (v or "").strip() for k, v in ligne.items() if k} for ligne in lecteur]


def lire_fichier(chemin: Path, session: str, texte: str | int) -> Collecte:
    documents, numeros = [], defaultdict(list)
    lignes = lignes_csv(chemin.read_bytes())
    for ligne in lignes:
        numero = ligne.get("Numéro", "")
        if trouve := NUMERO.match(numero):
            numeros[trouve["partie"] or "-"].append(int(trouve["n"]))
        dispositif, objet = texte_brut(ligne.get("Dispositif")), texte_brut(ligne.get("Objet"))
        if not dans_perimetre(dispositif, objet):
            continue
        sort = ligne.get("Sort") or None
        documents.append(
            DocumentBrut(
                source=Source.SENAT,
                identifiant=f"{session}/{texte}/{numero}",
                nature="AMENDEMENT",
                type_texte=TypeTexte.AMENDEMENT,
                titre=f"Amendement n° {numero}",
                date_document=_date(ligne.get("Date de dépôt")),
                url_officielle=ligne.get("Url amendement") or url_jeu_complet(session, texte),
                texte=normaliser(f"{dispositif}\nObjet :\n{objet}" if objet else dispositif),
                etat={"sort": sort, "date_sort": ligne.get("Date de saisie du sort")},
                meta={
                    "session": session,
                    "texte": str(texte),
                    "article": ligne.get("Subdivision"),
                    "auteur": ligne.get("Auteur"),
                },
                numero_amendement=numero,
                etape=etape_depuis_sort(sort),
                chemin_brut=chemin.name,
            )
        )
    ecarts, attendus, recus = [], 0, 0
    for partie, liste in sorted(numeros.items()):
        rapport = controler_numeros(liste, "amendement")
        attendus, recus = attendus + rapport.attendus, recus + rapport.recus
        ecarts += [f"partie {partie} : {e}" for e in rapport.ecarts]
    return Collecte(
        source=Source.SENAT,
        fichier=chemin.name,
        documents=documents,
        controle=Rapport(attendus=attendus, recus=recus, ecarts=ecarts),
        nb_lus=len(lignes),
    )


class ConnecteurSenat:
    """Un connecteur par texte suivi (projet de loi de finances, en séance ou en commission)."""

    source = Source.SENAT

    def __init__(
        self, dossier_brut: Path, session: str, texte: str | int, commission: bool = False
    ) -> None:
        self.dossier = dossier_brut / "senat"
        self.session, self.texte, self.commission = session, texte, commission

    def recuperer(self, depuis: date) -> Iterator[Collecte]:
        suffixe = "_commission" if self.commission else ""
        nom = f"jeu_complet_{self.session}_{self.texte}{suffixe}_{date.today():%Y%m%d}.csv"
        with client_http() as client:
            chemin = telecharger(
                client,
                url_jeu_complet(self.session, self.texte, self.commission),
                self.dossier / nom,
            )
        collecte = lire_fichier(chemin, self.session, self.texte)
        collecte.documents = [
            d for d in collecte.documents if not d.date_document or d.date_document >= depuis
        ]
        yield collecte
