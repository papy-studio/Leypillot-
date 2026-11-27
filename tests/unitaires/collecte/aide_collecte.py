"""Aides des tests du lot 1 : corpus de textes réels et archives reconstituées.

Les archives (JO, Assemblée, Sénat, BOFiP) sont fabriquées ici, au format des sources,
avec des identifiants, des dates et des sorts fictifs. Les textes du corpus sont de vrais
textes publics (loi de finances pour 2025, amendements), recopiés dans
``donnees_exemple/lot1_corpus``.
"""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

CORPUS = Path(__file__).parents[3] / "donnees_exemple" / "lot1_corpus"


def lire_corpus(nom: str) -> str:
    return (CORPUS / nom).read_text(encoding="utf-8")


def _ajouter(archive: tarfile.TarFile, nom: str, contenu: str | bytes) -> None:
    donnees = contenu.encode("utf-8") if isinstance(contenu, str) else contenu
    info = tarfile.TarInfo(nom)
    info.size = len(donnees)
    archive.addfile(info, io.BytesIO(donnees))


def _texte_jorf(ident: str, nature: str, titre: str, sequence: int, parution: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<TEXTE_VERSION><META>
<META_COMMUN><ID>{ident}</ID><ORIGINE>JORF</ORIGINE><NATURE>{nature}</NATURE></META_COMMUN>
<META_SPEC><META_TEXTE_CHRONICLE><CID>{ident}</CID><NUM>2025-127</NUM>
<NUM_SEQUENCE>{sequence}</NUM_SEQUENCE><NOR>ECOX0000000L</NOR><DATE_PUBLI>2025-02-15</DATE_PUBLI>
<DATE_TEXTE>2025-02-14</DATE_TEXTE><NUM_PARUTION>{parution}</NUM_PARUTION></META_TEXTE_CHRONICLE>
<META_TEXTE_VERSION><TITREFULL>{titre}</TITREFULL></META_TEXTE_VERSION></META_SPEC>
</META></TEXTE_VERSION>"""


def _article_jorf(ident: str, texte: str, num: str, lignes: list[str]) -> str:
    contenu = "".join(f"<p>{ligne}</p>" for ligne in lignes)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ARTICLE><META><META_COMMUN><ID>{ident}</ID></META_COMMUN>
<META_SPEC><META_ARTICLE><NUM>{num}</NUM></META_ARTICLE></META_SPEC></META>
<CONTEXTE><TEXTE cid="{texte}" nature="LOI"/></CONTEXTE>
<BLOC_TEXTUEL><CONTENU>{contenu}</CONTENU></BLOC_TEXTUEL></ARTICLE>"""


LOI = "JORFTEXT000000000101"
DECRET = "JORFTEXT000000000102"
ARTICLE_56 = [
    "I. – L’article 244 quater B du code général des impôts est ainsi modifié :",
    "1° À la fin de la quatrième phrase du premier alinéa du I, le taux : « 30 % » "
    "est remplacé par le taux : « 20 % » ;",
    "2° Au premier alinéa du k du II, l’année : « 2024 » est remplacée par l’année : « 2027 ».",
    "II. – Le 1° du I s’applique aux dépenses exposées à compter du 1er janvier 2025.",
]


def fabriquer_archive_jorf(dossier: Path, *, oublier_decret: bool = False) -> Path:
    """JO n° 40 du 15 février 2025, réduit à deux textes : la loi de finances (articles 55
    et 56, dans le désordre dans l'archive) et un décret hors périmètre."""
    chemin = dossier / "JORF_20250215-003012.tar.gz"
    with tarfile.open(chemin, "w:gz") as archive:
        _ajouter(
            archive,
            "jorf/global/JORFCONT000000000040.xml",
            """<JO><META><META_COMMUN><ID>JORFCONT000000000040</ID></META_COMMUN><META_SPEC>
            <META_CONTENEUR><TITRE>JORF n°0040 du 15 février 2025</TITRE><NUM>0040</NUM>
            <DATE_PUBLI>2025-02-15</DATE_PUBLI></META_CONTENEUR></META_SPEC></META>
            <STRUCTURE_TXT><TM niv="1"><TITRE_TM>Lois</TITRE_TM>"""
            f'<LIEN_TXT idtxt="{LOI}"/></TM><TM niv="1"><TITRE_TM>Décrets</TITRE_TM>'
            f'<LIEN_TXT idtxt="{DECRET}"/></TM></STRUCTURE_TXT></JO>',
        )
        _ajouter(
            archive,
            f"jorf/global/texte/version/{LOI}.xml",
            _texte_jorf(
                LOI, "LOI", "LOI n° 2025-127 du 14 février 2025 de finances pour 2025", 1, 40
            ),
        )
        _ajouter(
            archive,
            f"jorf/global/texte/struct/{LOI}.xml",
            f"<TEXTELR><META><META_COMMUN><ID>{LOI}</ID></META_COMMUN></META><STRUCT>"
            f'<LIEN_SECTION_TA id="JORFSCTA000000000001"/></STRUCT></TEXTELR>',
        )
        _ajouter(
            archive,
            "jorf/global/section_ta/JORFSCTA000000000001.xml",
            "<SECTION_TA><ID>JORFSCTA000000000001</ID><STRUCTURE_TA>"
            '<LIEN_ART id="JORFARTI000000000055" num="55"/>'
            '<LIEN_ART id="JORFARTI000000000056" num="56"/></STRUCTURE_TA></SECTION_TA>',
        )
        _ajouter(
            archive,
            "jorf/global/article/JORFARTI000000000056.xml",
            _article_jorf("JORFARTI000000000056", LOI, "56", ARTICLE_56),
        )
        _ajouter(
            archive,
            "jorf/global/article/JORFARTI000000000055.xml",
            _article_jorf(
                "JORFARTI000000000055",
                LOI,
                "55",
                [
                    "III. – À la première phrase du premier alinéa du 3° bis de l’article L. 80 B "
                    "du livre des procédures fiscales, la référence : « j » est remplacée par la "
                    "référence : « i »."
                ],
            ),
        )
        if not oublier_decret:
            _ajouter(
                archive,
                f"jorf/global/texte/version/{DECRET}.xml",
                _texte_jorf(
                    DECRET, "DECRET", "Décret relatif aux horaires des bibliothèques", 2, 40
                ),
            )
    return chemin


def amendement_an(numero: int, dispositif: str, sort: str | None = None) -> dict:
    return {
        "amendement": {
            "uid": f"AMANR5L17PO59048B0324P0D1N{numero:06d}",
            "texteLegislatifRef": "PRJLANR5L17B0324",
            "identification": {
                "numeroLong": f"I-{numero}",
                "numeroOrdreDepot": str(numero),
                "prefixeOrganeExamen": "AN",
            },
            "corps": {
                "contenuAuteur": {"dispositif": dispositif, "exposeSommaire": "<p>Exposé.</p>"}
            },
            "cycleDeVie": {
                "dateDepot": "2024-10-17",
                "sort": sort,
                "etatDesTraitements": "Discuté",
            },
            "pointeurFragmentTexte": {"division": {"articleDesignation": "Après l'article 13"}},
        }
    }


def fabriquer_archive_an(dossier: Path) -> Path:
    """Trois amendements, dont le n° 2211 du fil rouge ; le n° 2210 manque."""
    chemin = dossier / "Amendements.json.zip"
    i_2211 = "".join(f"<p>{ligne}</p>" for ligne in lire_corpus("an_I-2211.txt").splitlines())
    with zipfile.ZipFile(chemin, "w") as archive:
        for numero, corps, sort in (
            (2209, "<p>Supprimer l'article 5.</p>", "Rejeté"),
            (2211, i_2211, "Adopté"),
            (2212, "<p>Au début de l'article 3, ajouter un alinéa.</p>", None),
        ):
            archive.writestr(f"json/{numero}.json", json.dumps(amendement_an(numero, corps, sort)))
    return chemin
