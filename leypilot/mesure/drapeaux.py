"""Drapeau « à vérifier » du résumé S3.

Posé automatiquement quand :
- le texte renvoie à un décret (ou un arrêté) à paraître ;
- l'extraction S2 est marquée « à revoir » ;
- la condition modifiée contient des termes non définis dans le texte
  (heuristique : terme entre guillemets, sans chiffre, ni défini dans le texte
  ni présent dans le lexique fourni).
"""

from __future__ import annotations

import re

from leypilot.mesure.schemas import Changement
from leypilot.mesure.textes import normaliser

MOTIF_DECRET = "renvoi à un décret ou un arrêté à paraître"
MOTIF_EXTRACTION = "extraction S2 marquée « à revoir »"
MOTIF_TERMES = "termes non définis dans le texte"
MOTIF_CITATION = "citation introuvable mot pour mot dans le texte"
MOTIF_MONTANT = "montant absent de la citation"
MOTIF_DATE = "date du résumé incohérente avec la date d'application"

_RENVOI = re.compile(
    r"\b(?:fix|pr[ée]cis|d[ée]fini|d[ée]termin)\w*\s+par\s+(?:un\s+)?(?:d[ée]cret|arr[êe]t[ée])"
    r"|\bd[ée]cret\s+en\s+Conseil\s+d'[ÉE]tat"
    r"|\bpar\s+d[ée]cret\b"
    r"|\bun\s+d[ée]cret\s+(?:fixe|pr[ée]cise|d[ée]finit|d[ée]termine)",
    re.IGNORECASE,
)
_GUILLEMETS = re.compile(r"«\s*([^»]{2,80}?)\s*»|“([^”]{2,80})”")


def renvoie_a_un_decret(texte: str) -> bool:
    return bool(_RENVOI.search(normaliser(texte)))


def _est_defini(terme: str, texte: str) -> bool:
    terme = re.escape(terme)
    definitions = (
        rf"{terme}\s*»?\s*(?:s'entend|d[ée]signe|est\s+d[ée]fini|sont\s+d[ée]finis|correspond)",
        rf"(?:on\s+entend\s+par|est\s+consid[ée]r[ée]e?\s+comme)\s+«?\s*{terme}",
    )
    return any(re.search(motif, texte, re.IGNORECASE) for motif in definitions)


def termes_non_definis(changement: Changement, lexique: frozenset[str] = frozenset()) -> list[str]:
    texte = normaliser(changement.texte_source)
    connus = {terme.lower() for terme in lexique}
    termes = []
    for trouve in _GUILLEMETS.finditer(normaliser(changement.passage_cite)):
        terme = (trouve.group(1) or trouve.group(2)).strip()
        if any(c.isdigit() for c in terme) or terme.lower() in connus:
            continue  # « 30 % » est une valeur, pas un terme
        if not _est_defini(terme, texte) and terme not in termes:
            termes.append(terme)
    return termes


def detecter_doutes(changement: Changement, lexique: frozenset[str] = frozenset()) -> list[str]:
    motifs = []
    if renvoie_a_un_decret(changement.passage_cite) or renvoie_a_un_decret(changement.texte_source):
        motifs.append(MOTIF_DECRET)
    if changement.a_revoir:
        motifs.append(MOTIF_EXTRACTION)
    if termes := termes_non_definis(changement, lexique):
        motifs.append(f"{MOTIF_TERMES} : {', '.join(termes)}")
    return motifs
