"""S2 · Extraction déterministe des changements (formules législatives).

Une loi modifie le droit avec un petit nombre de formules figées : « le taux :
« 30 % » est remplacé par le taux : « 20 % » », « est ainsi rédigé », « est abrogé »…
Chaque formule a son expression régulière dans ``FORMULES``.

``extraire`` lit le texte ligne par ligne et suit les chapeaux (« L'article 244 quater B
du code général des impôts est ainsi modifié : ») pour savoir à quel article s'applique
chaque ligne. Chaque opération garde le passage exact, vérifiable mot pour mot.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from leypilot.collecte.cibles import CIBLES_ARTICLES
from leypilot.collecte.textes import normaliser

# ------------------------------------------------------------------ briques

LATIN = (
    r"(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|undecies|duodecies"
    r"|terdecies|quaterdecies|quindecies|sexdecies|septdecies)"
)
# Numéro d'article : « 244 quater B », « 44 sexies-0 A », « L. 80 B ». La lettre finale
# est sensible à la casse, sinon « du » ou « de » seraient lus comme suffixe.
ART = (
    rf"(?:L\.\s?|R\.\s?|D\.\s?)?\d+(?:-\d+)?(?:\s{LATIN}(?:-0)?)?(?-i:\s[A-Z]{{1,2}})?"
    rf"(?:\s{LATIN})?(?:-\d+)?(?![\w])"
)
CODE = (
    r"(?P<code>code général des impôts|livre des procédures fiscales|code monétaire et financier"
    r"|code de la sécurité sociale|loi n° [\d-]+ du \d+\w* \w+ \d{4}[^,;:]*?)"
)
REF_ARTICLE = re.compile(
    rf"(?:de l'article|à l'article|l'article|des articles|les articles)\s+(?P<art>{ART})"
    rf"(?:\s+(?:du|de la|des)\s+{CODE})?",
    re.IGNORECASE,
)
OBJ = (
    r"le taux|le montant|l'année|la date|le mot|les mots|la référence|les références"
    r"|le nombre|le pourcentage|la somme|le chiffre"
)


def _cite(nom: str) -> str:
    return rf"«\s*(?P<{nom}>[^»]*?)\s*»"


_FORMULES_SOURCE: tuple[tuple[str, str], ...] = (
    # Le guillemet fermant de l'ancienne valeur est facultatif : il manque dans
    # l'amendement AN I-2211 (fil rouge client B).
    (
        "remplacement",
        rf"(?P<objet>{OBJ})\s*:\s*«\s*(?P<ancien>[^«»]*?)\s*»?\s*(?:est|sont|et)\s+"
        rf"remplacée?s?\s+par\s+(?:{OBJ})\s*:\s*{_cite('nouveau')}",
    ),
    (
        "substitution_amendement",
        r"(?:à|a)\s+l'alinéa\s+(?P<alinea>\d+)\s*,\s*substituer\s+(?:au mot|aux mots"
        r"|à la référence|au taux|au montant|à l'année|au nombre)\s*:\s*«\s*(?P<ancien>[^»]*?)"
        r"\s*»\s*,\s*(?P<objet>le mot|les mots|la référence|le taux|le montant|l'année"
        r"|le nombre)\s*:\s*«\s*(?P<nouveau>.*)»",
    ),
    (
        "insertion_mots",
        rf"après\s+(?:{OBJ})\s*:\s*{_cite('repere')}\s*,?\s*(?:est|sont)\s+insérée?s?\s+"
        rf"(?P<objet>{OBJ})\s*:\s*{_cite('nouveau')}",
    ),
    (
        "suppression_fin",
        rf"après\s+(?P<objet>{OBJ})\s*:\s*{_cite('ancien')}\s*,\s*la fin "
        r"(?P<cible>[^;:«»]{1,80}?)\s+est\s+supprimée",
    ),
    (
        "suppression_mots",
        rf"(?P<objet>{OBJ})\s*:\s*{_cite('ancien')}\s*(?:est|sont)\s+supprimée?s?",
    ),
    ("suppression", r"^(?P<cible>(?:la|le|les)\s[^;:«»]{1,80}?)\s+(?:est|sont)\s+supprimée?s?"),
    ("abrogation", r"^(?P<cible>(?:la|le|les|l')\s?[^;:«»]{1,80}?)\s+(?:est|sont)\s+abrogée?s?"),
    (
        "insertion_subdivision",
        r"après\s+(?P<repere>[^,«»]{1,80}),\s*(?:il est|sont)\s+insérée?s?\s+"
        r"(?P<ajout>[^:«»]{1,60}?)\s+ainsi\s+rédigée?s?\s*:",
    ),
    (
        "complement_imperatif",
        r"^compléter\s+(?P<cible>[^:«»]{1,150}?)\s+par\s+(?P<ajout>[^:«»]{1,60}?)\s+"
        r"ainsi\s+rédigée?s?\s*:",
    ),
    (
        "complement",
        r"(?P<cible>[^;:«»]{1,150}?)\s+est\s+complétée?\s+par\s+(?P<ajout>[^:«»]{1,60}?)\s+"
        r"ainsi\s+rédigée?s?\s*:",
    ),
    ("redaction", r"(?P<cible>[^;:«»]{1,150}?)\s+(?:est|sont)\s+ainsi\s+rédigée?s?\s*:"),
)
FORMULES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (nom, re.compile(motif, re.IGNORECASE)) for nom, motif in _FORMULES_SOURCE
)
# Les cinq premières formules portent des valeurs entre guillemets : une ligne qui en
# contient une n'est jamais un simple chapeau.
_FORMULES_A_VALEURS = FORMULES[:5]

CHAPEAU = re.compile(
    r"(?P<cible>[^:;«»]{1,160}?)\s+(?:est|sont)\s+ainsi\s+modifiée?s?\s*:", re.IGNORECASE
)
CHAPEAU_LOC = re.compile(r"^(?P<cible>(?:à|au|aux|a)\s[^:«»]{1,100}?)\s*:$", re.IGNORECASE)
LOCALISATION = re.compile(r"^(?P<loc>(?:à|au|aux)\s[^,«»]{3,220}?),\s", re.IGNORECASE)
CLAUSE_APPLICATION = re.compile(
    r"(?:s'applique(?:nt)?|est applicable|sont applicables|entre(?:nt)? en vigueur)\b",
    re.IGNORECASE,
)

# ------------------------------------------------------------------ niveaux de numérotation

NIVEAUX: tuple[tuple[float, re.Pattern[str]], ...] = (
    (0, re.compile(r"^Article\s+\S+")),
    (1, re.compile(r"^[IVX]+\.\s*[–-]\s*")),
    (2, re.compile(r"^[A-Z]\.\s*[–-]\s*")),
    (3, re.compile(r"^\d+°\s*")),
    (4, re.compile(r"^[a-z]\)\s*")),
    (5, re.compile(r"^[–-]\s*")),
)
ENTETE_AMENDEMENT = re.compile(
    r"^(?:Insérer un article additionnel ainsi rédigé"
    r"|(?:Après|Avant) l'article \S+,? insérer l'article suivant)\s*:?$",
    re.IGNORECASE,
)
NIVEAU_LIBRE = 0.5  # phrase non numérotée : juste sous « Article »


def niveau(ligne: str) -> tuple[float, str]:
    """Niveau de numérotation d'une ligne et son contenu sans le numéro."""
    if ENTETE_AMENDEMENT.match(ligne):
        return 0, ""  # en-tête d'amendement : remet le contexte à zéro
    for rang, motif in NIVEAUX:
        if trouve := motif.match(ligne):
            return rang, ligne[trouve.end() :]
    return NIVEAU_LIBRE, ligne


# ------------------------------------------------------------------ articles visés

LISTE_ARTICLES = re.compile(
    r"(?:de l'article|à l'article|l'article|des articles|aux articles|les articles)\s+"
    rf"(?P<liste>{ART}(?:\s*(?:,|\bet\b)\s*{ART})*)(?:\s+(?:du|de la|des)\s+{CODE})?",
    re.IGNORECASE,
)
UN_ARTICLE = re.compile(ART)
_CITATIONS = re.compile(r"«[^»]*»")


def canon_code(code: str) -> str:
    """« loi n° 2003-1311 du 30 décembre 2003 de finances… » devient « loi n° 2003-1311 »."""
    trouve = re.match(r"loi n° ([\d-]+)", code)
    return f"loi n° {trouve.group(1)}" if trouve else code


def tous_articles(texte: str) -> list[tuple[str | None, str]]:
    """Articles désignés hors des passages entre guillemets (le nouveau texte n'est pas
    une cible), dans l'ordre, sans doublon."""
    vus: list[tuple[str | None, str]] = []
    for liste in LISTE_ARTICLES.finditer(_CITATIONS.sub("« »", texte)):
        code = canon_code(liste["code"]) if liste["code"] else None
        for article in UN_ARTICLE.finditer(liste["liste"]):
            cle = (code, article.group(0).strip())
            if cle[1] and cle not in vus:
                vus.append(cle)
    return vus


def lire_cible(texte: str) -> dict[str, str]:
    """Code, article et subdivision désignés par un morceau de phrase."""
    contexte: dict[str, str] = {}
    if trouve := REF_ARTICLE.search(texte):
        contexte["article"] = trouve["art"].strip()
        if trouve["code"]:
            contexte["code"] = canon_code(trouve["code"])
    if re.search(r"code général des impôts", texte, re.IGNORECASE):
        contexte["code"] = "code général des impôts"
    subdivision = re.match(
        r"^(?:le|la|les)\s+([IVX]+(?:\s(?:bis|ter))?|[a-z](?:\sbis)?|\d+°(?:\sbis)?)$",
        texte.strip(),
        re.IGNORECASE,
    )
    if subdivision:
        contexte["subdivision"] = subdivision.group(1)
    elif "article" not in contexte and "code" not in contexte and texte.strip():
        contexte["subdivision"] = texte.strip()  # ex. « La deuxième phrase du premier alinéa »
    return contexte


@dataclass
class _Contexte:
    code: str | None = None
    article: str | None = None
    subdivisions: list[str] = field(default_factory=list)


def _fusion(pile: list[tuple[float, dict[str, str]]]) -> _Contexte:
    contexte = _Contexte()
    for _, morceau in pile:
        contexte.code = morceau.get("code", contexte.code)
        contexte.article = morceau.get("article", contexte.article)
        if "subdivision" in morceau:
            contexte.subdivisions.append(morceau["subdivision"])
    return contexte


# ------------------------------------------------------------------ extraction


@dataclass
class Operation:
    """Opération lue dans un texte, avant validation (voir ``schemas.depuis_operation``)."""

    operation: str
    code: str | None
    article: str | None
    localisation: str
    objet: str | None
    ancien: str | None
    nouveau: str | None
    passage: str
    articles: list[tuple[str | None, str]]
    alinea_projet: int | None = None
    clauses_application: list[str] = field(default_factory=list)


def _valeur(trouve: re.Match[str], nom: str) -> str | None:
    valeur = (trouve.groupdict().get(nom) or "").strip()
    return valeur or None


def extraire(texte: str) -> list[Operation]:
    """Opérations détectées dans un texte.

    Chaque opération reçoit aussi, telles quelles, les clauses d'application du même
    article de loi (« … s'applique aux dépenses exposées à compter du … ») : le lot 1 les
    recopie, la personne 2 en tire les dates, la personne 3 les conditions.
    """
    operations: list[tuple[int, Operation]] = []
    pile: list[tuple[float, dict[str, str]]] = []
    bloc = 0
    clauses: dict[int, list[str]] = {}
    for ligne in normaliser(texte).splitlines():
        rang, corps = niveau(ligne)
        if rang == 0:
            pile, bloc = [], bloc + 1
            continue
        if CLAUSE_APPLICATION.search(corps) and not any(m.search(corps) for _, m in FORMULES):
            clauses.setdefault(bloc, []).append(ligne)
            continue
        while pile and pile[-1][0] >= rang:
            pile.pop()
        chapeau = CHAPEAU.search(corps) or CHAPEAU_LOC.match(corps)
        if chapeau and not any(m.search(corps) for _, m in _FORMULES_A_VALEURS):
            pile.append((rang, lire_cible(chapeau["cible"])))
            continue
        contexte = _fusion(pile)
        localisation = LOCALISATION.match(corps)
        propre = lire_cible(corps)
        occupe: list[tuple[int, int]] = []
        for nom, motif in FORMULES:
            for trouve in motif.finditer(corps):
                if any(trouve.start() < fin and debut < trouve.end() for debut, fin in occupe):
                    continue  # déjà couvert par une formule plus précise
                occupe.append((trouve.start(), trouve.end()))
                code = propre.get("code") or contexte.code
                liste = tous_articles(corps)
                if not liste and contexte.article:
                    liste = [(None, contexte.article)]
                liste = [(c or code, a) for c, a in liste]
                dans_cible = [cle for cle in liste if cle in CIBLES_ARTICLES]
                article = (dans_cible or liste or [(None, None)])[0][1]
                if dans_cible:
                    code = dans_cible[0][0]
                alinea = _valeur(trouve, "alinea")
                operations.append(
                    (
                        bloc,
                        Operation(
                            operation=nom,
                            code=code,
                            article=article,
                            localisation=" > ".join(
                                contexte.subdivisions
                                + ([localisation["loc"]] if localisation else [])
                            ),
                            objet=_valeur(trouve, "objet"),
                            ancien=_valeur(trouve, "ancien"),
                            nouveau=_valeur(trouve, "nouveau"),
                            passage=trouve.group(0),
                            articles=liste,
                            alinea_projet=int(alinea) if alinea else None,
                        ),
                    )
                )
    for numero_bloc, operation in operations:
        operation.clauses_application = list(clauses.get(numero_bloc, []))
    return [operation for _, operation in operations]
