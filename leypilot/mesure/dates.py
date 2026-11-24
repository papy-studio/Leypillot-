"""A4 · Dater : date d'entrée en vigueur et compte à rebours.

1. Expressions régulières sur les clauses d'application (dans le passage cité,
   puis dans tout le texte) → date **certaine**.
2. En secours, le LLM extrait la clause en JSON (vérifiée mot pour mot).
3. À défaut, droit commun : lendemain de la publication → date **estimée**.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel

from leypilot.commun.llm import ErreurLLM, ServiceLLM
from leypilot.mesure.schemas import Changement, NatureDate
from leypilot.mesure.textes import MOIS, citation_verifiee, normaliser, sans_accents

journal = logging.getLogger(__name__)

_A = r"[àa]"
_DATE = (
    r"(?P<jour>\d{1,2})(?:er)?\s+(?P<mois>janvier|f[ée]vrier|mars|avril|mai|juin|juillet"
    r"|ao[ûu]t|septembre|octobre|novembre|d[ée]cembre)\s+(?P<annee>\d{4})"
    r"|(?P<jour_n>\d{1,2})/(?P<mois_n>\d{1,2})/(?P<annee_n>\d{4})"
)

CLAUSES: list[tuple[str, re.Pattern[str]]] = [
    (
        "depenses",
        re.compile(
            rf"d[ée]penses\s+(?:expos[ée]es|engag[ée]es|r[ée]alis[ée]es)\s+{_A}\s+(?:compter|partir)"
            rf"\s+du\s+(?:{_DATE})",
            re.IGNORECASE,
        ),
    ),
    (
        "exercices_clos",
        re.compile(rf"exercices\s+clos\s+{_A}\s+(?:compter|partir)\s+du\s+(?:{_DATE})", re.I),
    ),
    (
        "exercices_ouverts",
        re.compile(rf"exercices\s+ouverts\s+{_A}\s+(?:compter|partir)\s+du\s+(?:{_DATE})", re.I),
    ),
    (
        "entree_en_vigueur",
        re.compile(rf"entre(?:nt)?\s+en\s+vigueur\s+le\s+(?:{_DATE})", re.IGNORECASE),
    ),
    ("a_compter_du", re.compile(rf"{_A}\s+(?:compter|partir)\s+du\s+(?:{_DATE})", re.I)),
]

CLAUSES_RELATIVES: list[tuple[str, re.Pattern[str], int]] = [
    (
        "lendemain_publication",
        re.compile(
            r"(?:entre(?:nt)?\s+en\s+vigueur|s'applique(?:nt)?)\s+le\s+lendemain\s+de\s+"
            r"(?:sa|leur|la)\s+publication",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        "publication",
        re.compile(
            rf"(?:{_A}\s+compter\s+de|d[èe]s)\s+(?:sa|leur|la)\s+publication", re.IGNORECASE
        ),
        0,
    ),
]


@dataclass(frozen=True)
class DateVigueur:
    date: date
    nature: NatureDate
    clause: str | None
    type_clause: str
    methode: str  # regex, llm ou droit_commun


class DateLLM(BaseModel):
    clause: str | None = None
    date: dt.date | None = None  # dt.date : le nom du champ masquerait le type date


def _date_depuis(trouve: re.Match[str]) -> date | None:
    try:
        if trouve["jour"]:
            mois = MOIS[sans_accents(trouve["mois"]).lower()]
            return date(int(trouve["annee"]), mois, int(trouve["jour"]))
        return date(int(trouve["annee_n"]), int(trouve["mois_n"]), int(trouve["jour_n"]))
    except (KeyError, ValueError):
        return None


def premiere_date(texte: str) -> date | None:
    trouve = re.search(_DATE, normaliser(texte), re.IGNORECASE)
    return _date_depuis(trouve) if trouve else None


def chercher_clause(texte: str, date_publication: date | None = None) -> DateVigueur | None:
    texte = normaliser(texte)
    for type_clause, motif in CLAUSES:
        for trouve in motif.finditer(texte):
            jour = _date_depuis(trouve)
            if jour is not None:
                return DateVigueur(jour, NatureDate.CERTAINE, trouve.group(0), type_clause, "regex")
    if date_publication is not None:
        for type_clause, motif, decalage in CLAUSES_RELATIVES:
            if trouve := motif.search(texte):
                jour = date_publication + timedelta(days=decalage)
                return DateVigueur(jour, NatureDate.CERTAINE, trouve.group(0), type_clause, "regex")
    return None


def _dater_par_llm(changement: Changement, service: ServiceLLM) -> DateVigueur | None:
    try:
        reponse = service.generer(
            "a4_date",
            DateLLM,
            {
                "texte": changement.texte_source,
                "article_vise": changement.article_vise,
                "parametre": changement.parametre,
            },
        )
    except ErreurLLM as erreur:
        journal.info("A4 : secours LLM indisponible (%s).", erreur)
        return None
    if reponse.date is None or not citation_verifiee(reponse.clause, changement.texte_source):
        return None
    lue = premiere_date(reponse.clause or "")
    nature = NatureDate.CERTAINE if lue == reponse.date else NatureDate.ESTIMEE
    return DateVigueur(reponse.date, nature, reponse.clause, "llm", "llm")


def dater(
    changement: Changement,
    *,
    date_publication: date | None = None,
    service_llm: ServiceLLM | None = None,
) -> DateVigueur | None:
    for zone in (changement.passage_cite, changement.texte_source):
        if trouvee := chercher_clause(zone, date_publication):
            return trouvee
    if service_llm is not None and (trouvee := _dater_par_llm(changement, service_llm)):
        return trouvee
    if date_publication is not None:
        # Droit commun (art. 1er du code civil) : à défaut de date, le lendemain de la publication.
        return DateVigueur(
            date_publication + timedelta(days=1),
            NatureDate.ESTIMEE,
            None,
            "droit_commun",
            "droit_commun",
        )
    return None


def jours_restants(date_vigueur: date, aujourd_hui: date) -> int:
    """Compte à rebours : négatif si la date est passée."""
    return (date_vigueur - aujourd_hui).days
