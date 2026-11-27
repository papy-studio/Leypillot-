"""Connecteur JO : archives quotidiennes de la DILA (fonds JORF, open data).

Adresse : https://echanges.dila.gouv.fr/OPENDATA/JORF/ (une archive ``JORF_AAAAMMJJ-HHMMSS.tar.gz``
par publication ; l'archive de la nuit, vers 0 h 30, contient le JO du jour).

Dans une archive :

- ``JORFCONT…`` : le sommaire d'un numéro du JO (liste des textes, ``LIEN_TXT/@idtxt``) ;
- ``JORFTEXT…`` : un texte (nature, NOR, numéro de parution, numéro de séquence, titre) ;
  le fichier ``struct`` donne l'ordre des articles ;
- ``JORFARTI…`` : un article (numéro, contenu HTML, texte parent dans ``CONTEXTE/TEXTE/@cid``) ;
- ``JORFSCTA…`` : une section (titre, articles qu'elle contient).

Le contrôle de complétude compare le sommaire aux textes reçus (test du JO n° 273 du
22 novembre 2026 : 65 textes annoncés, 65 reçus, séquences 1 à 65).

À vérifier sur une vraie archive avant la mise en service : les tests de ce module
utilisent une archive reconstituée, et la structure XML de la DILA peut varier.
"""

from __future__ import annotations

import re
import tarfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from leypilot.collecte.cibles import dans_perimetre
from leypilot.collecte.completude import Rapport, controler_sommaire
from leypilot.collecte.sources.base import (
    Collecte,
    DocumentBrut,
    Source,
    TypeTexte,
    client_http,
    telecharger,
)
from leypilot.collecte.textes import normaliser, texte_brut

URL_JORF = "https://echanges.dila.gouv.fr/OPENDATA/JORF/"
NOM_ARCHIVE = re.compile(r"JORF_(\d{8})-(\d{6})\.tar\.gz")
URL_LEGIFRANCE = "https://www.legifrance.gouv.fr/jorf/id/{}"

NATURES: dict[str, TypeTexte] = {
    "LOI": TypeTexte.LOI,
    "LOI_ORGANIQUE": TypeTexte.LOI,
    "ORDONNANCE": TypeTexte.ORDONNANCE,
    "DECRET": TypeTexte.DECRET,
    "DECRET_LOI": TypeTexte.DECRET,
    "ARRETE": TypeTexte.ARRETE,
}


# ------------------------------------------------------------------ lecture XML


def _local(balise: str) -> str:
    return balise.rsplit("}", 1)[-1]


def _premier(racine: ET.Element, nom: str) -> str | None:
    """Texte du premier élément ``nom`` (espaces de noms ignorés)."""
    for element in racine.iter():
        if _local(element.tag) == nom and (element.text or "").strip():
            return element.text.strip()  # type: ignore[union-attr]
    return None


def _contenu_html(element: ET.Element | None) -> str:
    if element is None:
        return ""
    interieur = (element.text or "") + "".join(
        ET.tostring(enfant, encoding="unicode") for enfant in element
    )
    return texte_brut(interieur)


def _date(valeur: str | None) -> date | None:
    if not valeur or valeur.startswith("2999"):
        return None
    try:
        return date.fromisoformat(valeur[:10])
    except ValueError:
        return None


def _entier(valeur: str | None) -> int | None:
    return int(valeur) if valeur and valeur.strip().isdigit() else None


@dataclass
class _Texte:
    identifiant: str
    nature: str = ""
    titre: str | None = None
    nor: str | None = None
    eli: str | None = None
    num: str | None = None
    num_parution: int | None = None
    num_sequence: int | None = None
    date_publi: date | None = None
    date_texte: date | None = None
    ordre_articles: list[str] = field(default_factory=list)
    chemin: str = ""


@dataclass
class _Article:
    identifiant: str
    texte_cid: str | None
    num: str | None
    contenu: str


@dataclass
class ContenuArchive:
    """Ce qu'une archive DILA contient, une fois lu."""

    sommaires: dict[str, list[str]] = field(default_factory=dict)  # n° de JO -> JORFTEXT
    dates_jo: dict[str, date | None] = field(default_factory=dict)
    textes: dict[str, _Texte] = field(default_factory=dict)
    articles: dict[str, _Article] = field(default_factory=dict)
    sections: dict[str, list[str]] = field(default_factory=dict)  # JORFSCTA -> enfants


def _enfants_structure(racine: ET.Element) -> list[str]:
    """Identifiants des articles et sections liés, dans l'ordre du document."""
    return [
        element.get("id", "")
        for element in racine.iter()
        if _local(element.tag) in {"LIEN_ART", "LIEN_SECTION_TA"} and element.get("id")
    ]


def lire_archive(chemin: Path) -> ContenuArchive:
    """Lit une archive ``.tar.gz`` en mémoire, sans rien extraire sur le disque."""
    contenu = ContenuArchive()
    with tarfile.open(chemin, "r:gz") as archive:
        for membre in archive:
            if not (membre.isfile() and membre.name.endswith(".xml")):
                continue
            fichier = archive.extractfile(membre)
            if fichier is None:
                continue
            racine = ET.fromstring(fichier.read())
            identifiant = _premier(racine, "ID") or Path(membre.name).stem
            if identifiant.startswith("JORFCONT"):
                numero = (_premier(racine, "NUM") or "").lstrip("0") or identifiant
                contenu.sommaires[numero] = [
                    element.get("idtxt", "")
                    for element in racine.iter()
                    if _local(element.tag) == "LIEN_TXT" and element.get("idtxt")
                ]
                contenu.dates_jo[numero] = _date(_premier(racine, "DATE_PUBLI"))
            elif identifiant.startswith("JORFTEXT"):
                texte = contenu.textes.setdefault(identifiant, _Texte(identifiant))
                if "/struct/" in membre.name or _local(racine.tag) == "TEXTELR":
                    texte.ordre_articles = _enfants_structure(racine)
                    continue
                texte.nature = _premier(racine, "NATURE") or texte.nature
                texte.titre = _premier(racine, "TITREFULL") or _premier(racine, "TITRE")
                texte.nor = _premier(racine, "NOR")
                texte.eli = _premier(racine, "ID_ELI") or _premier(racine, "ELI")
                texte.num = _premier(racine, "NUM")
                texte.num_parution = _entier(_premier(racine, "NUM_PARUTION"))
                texte.num_sequence = _entier(_premier(racine, "NUM_SEQUENCE"))
                texte.date_publi = _date(_premier(racine, "DATE_PUBLI"))
                texte.date_texte = _date(_premier(racine, "DATE_TEXTE"))
                texte.chemin = f"{chemin.name}#{membre.name}"
            elif identifiant.startswith("JORFARTI"):
                parent = next(
                    (e.get("cid") for e in racine.iter() if _local(e.tag) == "TEXTE"), None
                )
                bloc = next((e for e in racine.iter() if _local(e.tag) == "CONTENU"), None)
                contenu.articles[identifiant] = _Article(
                    identifiant, parent, _premier(racine, "NUM"), _contenu_html(bloc)
                )
            elif identifiant.startswith("JORFSCTA"):
                contenu.sections[identifiant] = _enfants_structure(racine)
    return contenu


def _cle_naturelle(article: _Article) -> tuple[int, str]:
    trouve = re.match(r"\d+", article.num or "")
    return (int(trouve.group(0)) if trouve else 10**6, article.num or "")


def _articles_dans_ordre(contenu: ContenuArchive, texte: _Texte) -> list[_Article]:
    """Articles d'un texte : ordre du fichier ``struct`` (sections dépliées), sinon
    ordre des numéros. Les articles absents de la structure sont ajoutés à la fin."""
    du_texte = [a for a in contenu.articles.values() if a.texte_cid == texte.identifiant]
    ordre: list[str] = []

    def deplier(identifiants: list[str], profondeur: int = 0) -> None:
        for ident in identifiants:
            if ident in contenu.sections and profondeur < 20:
                deplier(contenu.sections[ident], profondeur + 1)
            elif ident not in ordre:
                ordre.append(ident)

    deplier(texte.ordre_articles)
    rang = {ident: i for i, ident in enumerate(ordre)}
    return sorted(du_texte, key=lambda a: (rang.get(a.identifiant, len(rang)), _cle_naturelle(a)))


def corps_du_texte(contenu: ContenuArchive, texte: _Texte) -> str:
    """Texte complet : « Article N » puis le contenu de l'article, pour chaque article."""
    morceaux = []
    for article in _articles_dans_ordre(contenu, texte):
        morceaux.append(f"Article {article.num}" if article.num else "Article")
        morceaux.append(article.contenu)
    return normaliser("\n".join(morceaux))


def documents_et_controle(contenu: ContenuArchive, nom_archive: str) -> Collecte:
    """Documents du périmètre et contrôle de complétude de chaque numéro du JO."""
    ecarts: list[str] = []
    attendus = recus = 0
    for numero, annonces in contenu.sommaires.items():
        du_numero = [t for t in contenu.textes.values() if t.num_parution == _entier(numero)]
        rapport = controler_sommaire(
            annonces,
            [t.identifiant for t in contenu.textes.values() if t.identifiant in annonces]
            + [t.identifiant for t in du_numero],
            [t.num_sequence for t in du_numero if t.num_sequence],
        )
        attendus, recus = attendus + rapport.attendus, recus + rapport.recus
        ecarts += [f"JO n° {numero} : {ecart}" for ecart in rapport.ecarts]

    documents = []
    for texte in contenu.textes.values():
        corps = corps_du_texte(contenu, texte)
        if not dans_perimetre(texte.titre, corps):
            continue
        documents.append(
            DocumentBrut(
                source=Source.JORF,
                identifiant=texte.identifiant,
                nature=texte.nature,
                type_texte=NATURES.get(texte.nature, TypeTexte.DECRET),
                titre=texte.titre,
                date_document=texte.date_publi or texte.date_texte,
                url_officielle=URL_LEGIFRANCE.format(texte.identifiant),
                texte=corps,
                etat={"date_publi": texte.date_publi, "num_parution": texte.num_parution},
                meta={
                    "num": texte.num,
                    "num_parution": texte.num_parution,
                    "num_sequence": texte.num_sequence,
                    "date_texte": texte.date_texte,
                },
                nor=texte.nor,
                eli=texte.eli,
                chemin_brut=texte.chemin,
            )
        )
    return Collecte(
        source=Source.JORF,
        fichier=nom_archive,
        documents=documents,
        controle=Rapport(attendus=attendus, recus=recus, ecarts=ecarts),
        nb_lus=len(contenu.textes),
    )


def archives_publiees(page_html: str, depuis: date) -> list[str]:
    """Noms des archives listées dans la page de la DILA, publiées depuis ``depuis``."""
    noms = sorted(set(NOM_ARCHIVE.findall(page_html)))
    return [
        f"JORF_{jour}-{heure}.tar.gz"
        for jour, heure in noms
        if datetime.strptime(jour, "%Y%m%d").date() >= depuis
    ]


class ConnecteurJORF:
    source = Source.JORF

    def __init__(self, dossier_brut: Path, url: str = URL_JORF) -> None:
        self.dossier = dossier_brut / "jorf"
        self.url = url

    def recuperer(self, depuis: date) -> Iterator[Collecte]:
        with client_http() as client:
            page = client.get(self.url)
            page.raise_for_status()
            for nom in archives_publiees(page.text, depuis):
                chemin = self.dossier / nom
                if not chemin.exists():
                    telecharger(client, self.url + nom, chemin)
                yield self.lire(chemin)

    def lire(self, chemin: Path) -> Collecte:
        return documents_et_controle(lire_archive(chemin), chemin.name)


def lire_fichier(chemin: Path) -> Collecte:
    """Lecture d'une archive déjà téléchargée (outil en ligne de commande, tests)."""
    return documents_et_controle(lire_archive(chemin), chemin.name)


def textes_par_numero(contenu: ContenuArchive) -> dict[int | None, list[str]]:
    """Aide au diagnostic : textes reçus regroupés par numéro de parution."""
    groupes: dict[int | None, list[str]] = defaultdict(list)
    for texte in contenu.textes.values():
        groupes[texte.num_parution].append(texte.identifiant)
    return dict(groupes)
