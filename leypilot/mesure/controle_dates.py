"""Contrôle des dates du résumé S3, sans LLM.

Le pendant du filtre anti-montant pour les dates. Un résumé est refusé quand :
- la date d'application connue n'y figure pas ;
- il contient une date qui n'est ni la date d'application ni une date de la citation ;
- il fait dépendre l'application d'une étape de la procédure (« dès la publication »,
  « dès que la mesure est votée »…) alors que ni la citation ni la clause ne le disent ;
- il présente comme certaine une date seulement estimée.

Chaque erreur est une phrase : elle sert de motif dans le journal et de remarque au
LLM quand on lui demande de corriger sa réponse.
"""

from __future__ import annotations

import re
from datetime import date

from leypilot.mesure.dates import DateVigueur
from leypilot.mesure.schemas import NatureDate
from leypilot.mesure.textes import MOIS, date_en_francais, normaliser, sans_accents

_DATE_EN_LETTRES = re.compile(
    rf"\b(1er|\d{{1,2}})\s+({'|'.join(MOIS)})\s+(\d{{4}})\b", re.IGNORECASE
)
_DATE_NUMERIQUE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

_ETAPE = r"(?:publication|vote|adoption|promulgation)\b"
_APPLICATION_LIEE_A_UNE_ETAPE = re.compile(
    # « entre en vigueur dès la publication », « s'applique après son adoption »…
    r"(?:s'appliqu\w*|applicable\w*|entre\w*\s+en\s+vigueur|prend\w*\s+effet|effecti\w+)"
    r"\W+(?:\w+\W+){0,5}?"
    r"(?:des|a\s+compter\s+d[eu]|a\s+partir\s+d[eu]|apres|lors\s+d[eu]|au\s+moment\s+d[eu])"
    rf"\s+(?:la\s+|sa\s+|le\s+|son\s+|l')?{_ETAPE}"
    # « dès que la mesure est votée », « dès qu'elle sera publiée »…
    r"|\bdes\s+qu(?:e\s+|')(?:la\s+mesure|le\s+texte|la\s+loi|l'amendement|elle|il)\s+"
    r"(?:est|sera|aura\s+ete)\s+(?:votee?|adoptee?|publiee?|promulguee?)",
    re.IGNORECASE,
)
_MOTS_ESTIMATION = ("estim", "a confirmer", "sous reserve", "previsionnel")

DATE_ABSENTE = "la date d'application ({}) n'apparaît pas"
DATE_NON_JUSTIFIEE = "la date {} n'est ni la date d'application ni une date de la citation"
APPLICATION_LIEE_A_UNE_ETAPE = (
    "l'application est rattachée à une étape de la procédure (« {} ») : "
    "seule la date d'application dit quand la mesure s'applique"
)
DATE_ESTIMEE_PRESENTEE_COMME_CERTAINE = (
    "la date d'application est seulement estimée : il faut dire qu'elle est à confirmer"
)


def _simplifier(texte: str) -> str:
    # NFKC (dans normaliser) transforme déjà « 1ᵉʳ » en « 1er ».
    return sans_accents(normaliser(texte)).lower()


def _extrait(texte: str, trouve: re.Match[str]) -> str:
    """Passage trouvé, avec ses accents quand les positions le permettent."""
    original = normaliser(texte)
    if len(original) == len(trouve.string):  # sans_accents garde un caractère par caractère
        return original[trouve.start() : trouve.end()]
    return trouve.group(0)


def extraire_dates(texte: str) -> set[date]:
    """Dates écrites dans le texte : « 1er janvier 2026 », « 01/01/2026 », « 2026-01-01 »."""
    simple = _simplifier(texte)
    trouvees: list[tuple[int, int, int]] = []
    for jour, mois, annee in _DATE_EN_LETTRES.findall(simple):
        trouvees.append((int(annee), MOIS[mois], 1 if jour == "1er" else int(jour)))
    for jour, mois, annee in _DATE_NUMERIQUE.findall(simple):
        trouvees.append((int(annee), int(mois), int(jour)))
    for annee, mois, jour in _DATE_ISO.findall(simple):
        trouvees.append((int(annee), int(mois), int(jour)))
    dates = set()
    for annee, mois, jour in trouvees:
        try:
            dates.add(date(annee, mois, jour))
        except ValueError:
            continue  # « 31/02/2026 » : pas une date
    return dates


def erreurs_de_date(texte: str, citation: str, date_vigueur: DateVigueur | None) -> list[str]:
    """Erreurs de date du résumé ``texte`` (liste vide si le résumé est correct)."""
    erreurs = []
    dates = extraire_dates(texte)
    autorisees = extraire_dates(citation)

    if date_vigueur is not None:
        autorisees.add(date_vigueur.date)
        if date_vigueur.date not in dates:
            erreurs.append(DATE_ABSENTE.format(date_en_francais(date_vigueur.date)))
        simple = _simplifier(texte)
        if date_vigueur.nature == NatureDate.ESTIMEE and not any(
            mot in simple for mot in _MOTS_ESTIMATION
        ):
            erreurs.append(DATE_ESTIMEE_PRESENTEE_COMME_CERTAINE)

    for inconnue in sorted(dates - autorisees):
        erreurs.append(DATE_NON_JUSTIFIEE.format(date_en_francais(inconnue)))

    # Rattacher l'application à une étape n'est permis que si le texte officiel le fait.
    clause = date_vigueur.clause if date_vigueur is not None and date_vigueur.clause else ""
    sources = f"{citation} {clause}"
    if not _APPLICATION_LIEE_A_UNE_ETAPE.search(_simplifier(sources)):
        if trouve := _APPLICATION_LIEE_A_UNE_ETAPE.search(_simplifier(texte)):
            erreurs.append(APPLICATION_LIEE_A_UNE_ETAPE.format(_extrait(texte, trouve)))
    return erreurs
