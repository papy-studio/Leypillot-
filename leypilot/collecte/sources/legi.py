"""Connecteur LEGI : articles consolidés des codes (fichiers DILA, fonds LEGI).

Adresse : https://echanges.dila.gouv.fr/OPENDATA/LEGI/ (archives ``LEGI_AAAAMMJJ-HHMMSS.tar.gz``).
Un fichier ``LEGIARTI…`` par version d'article : numéro (``NUM``), état (``ETAT`` :
VIGUEUR, VIGUEUR_DIFF, ABROGE, ABROGE_DIFF, MODIFIE, MODIFIE_MORT_NE), dates de
vigueur, code parent (``CONTEXTE/TEXTE/@cid``), contenu, et liens vers le texte du JO
qui l'a modifié (``LIENS/LIEN``).

On ne garde que les articles de la table cible. Un même article garde le même
identifiant de document d'une version à l'autre (« code/numéro »), pour que la table
``document`` enchaîne ses versions et que ``legi.comparer`` voie l'avant et l'après.

À vérifier sur une vraie archive avant la mise en service (tests sur archive reconstituée).
"""

from __future__ import annotations

import tarfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from leypilot.collecte.cibles import CGI, est_cible
from leypilot.collecte.completude import Rapport
from leypilot.collecte.sources.base import (
    Collecte,
    DocumentBrut,
    Source,
    TypeTexte,
    client_http,
    telecharger,
)
from leypilot.collecte.sources.dila import archives_publiees, contenu_html, jour, local, premier

URL_LEGI = "https://echanges.dila.gouv.fr/OPENDATA/LEGI/"
URL_ARTICLE = "https://www.legifrance.gouv.fr/codes/article_lc/{}"

# Identifiant LEGI du code -> nom utilisé dans la table cible.
CODES = {"LEGITEXT000006069577": CGI}

# Une archive peut contenir l'ancienne version (passée à MODIFIE) et la nouvelle :
# seules les versions « actuelles » sont gardées.
ETATS_ACTUELS = {"VIGUEUR", "VIGUEUR_DIFF", "ABROGE", "ABROGE_DIFF"}
ETATS_ABROGES = {"ABROGE", "ABROGE_DIFF"}


@dataclass
class ArticleLegi:
    legiarti: str
    code: str
    num: str
    etat: str
    date_debut: date | None
    date_fin: date | None
    contenu: str
    liens_modificateurs: list[dict[str, str]]
    chemin: str


def lire_article(racine: ET.Element, chemin: str) -> ArticleLegi | None:
    cid = next((e.get("cid") for e in racine.iter() if local(e.tag) == "TEXTE"), None)
    code, num = CODES.get(cid or ""), premier(racine, "NUM")
    if code is None or num is None:
        return None
    bloc = next((e for e in racine.iter() if local(e.tag) == "BLOC_TEXTUEL"), None)
    contenu = (
        next((e for e in bloc.iter() if local(e.tag) == "CONTENU"), None)
        if bloc is not None
        else None
    )
    liens = [
        dict(e.attrib)
        for e in racine.iter()
        if local(e.tag) == "LIEN" and e.get("typelien") == "MODIFIE" and e.get("sens") == "source"
    ]
    return ArticleLegi(
        legiarti=premier(racine, "ID") or Path(chemin).stem,
        code=code,
        num=num,
        etat=premier(racine, "ETAT") or "",
        date_debut=jour(premier(racine, "DATE_DEBUT")),
        date_fin=jour(premier(racine, "DATE_FIN")),
        contenu=contenu_html(contenu),
        liens_modificateurs=liens,
        chemin=chemin,
    )


def document_article(article: ArticleLegi) -> DocumentBrut:
    jorf = [lien["cidtexte"] for lien in article.liens_modificateurs if lien.get("cidtexte")]
    return DocumentBrut(
        source=Source.LEGI,
        identifiant=f"{article.code}/{article.num}",
        nature="ARTICLE",
        type_texte=TypeTexte.VERSION_CONSOLIDEE,
        titre=f"Article {article.num} du {article.code}",
        date_document=article.date_debut,
        url_officielle=URL_ARTICLE.format(article.legiarti),
        # Un article abrogé peut n'avoir plus de contenu : son intitulé tient lieu de texte.
        texte=article.contenu or f"Article {article.num} ({article.etat.lower()})",
        etat={"etat": article.etat, "date_debut": article.date_debut, "date_fin": article.date_fin},
        meta={"legiarti": article.legiarti, "num": article.num, "jorf_modificateurs": jorf},
        chemin_brut=article.chemin,
    )


def lire_archive(chemin: Path) -> Collecte:
    retenus: dict[str, ArticleLegi] = {}
    lus = 0
    with tarfile.open(chemin, "r:gz") as archive:
        for membre in archive:
            if not (membre.isfile() and Path(membre.name).name.startswith("LEGIARTI")):
                continue
            fichier = archive.extractfile(membre)
            if fichier is None:
                continue
            lus += 1
            article = lire_article(ET.fromstring(fichier.read()), f"{chemin.name}#{membre.name}")
            if article is None or article.etat not in ETATS_ACTUELS:
                continue
            if not est_cible(article.code, article.num):
                continue
            cle = f"{article.code}/{article.num}"
            # Deux versions actuelles (en vigueur et à venir) : on garde la plus récente.
            ancienne = retenus.get(cle)
            if ancienne is None or (article.date_debut or date.min) > (
                ancienne.date_debut or date.min
            ):
                retenus[cle] = article
    return Collecte(
        source=Source.LEGI,
        fichier=chemin.name,
        documents=[document_article(a) for a in retenus.values()],
        controle=Rapport(attendus=0, recus=0),
        nb_lus=lus,
    )


class ConnecteurLEGI:
    source = Source.LEGI

    def __init__(self, dossier_brut: Path, url: str = URL_LEGI) -> None:
        self.dossier = dossier_brut / "legi"
        self.url = url

    def recuperer(self, depuis: date) -> Iterator[Collecte]:
        with client_http() as client:
            page = client.get(self.url)
            page.raise_for_status()
            for nom in archives_publiees(page.text, depuis, "LEGI"):
                chemin = self.dossier / nom
                if not chemin.exists():
                    telecharger(client, self.url + nom, chemin)
                yield lire_archive(chemin)
