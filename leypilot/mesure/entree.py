"""Contrat d'entrée P1 → P2 : documents filtrés et changements détectés.

D'après la répartition, la personne 1 fournit :
- les **documents filtrés** (texte, type de texte, date, identifiants officiels) ;
- les **changements** (dispositif, paramètre, ancienne et nouvelle valeur, passage cité),
  chacun rattaché à son document.

Ce module assemble les deux en un ``Changement``, le format de travail du lot 2.
Contrat provisoire : à valider avec la personne 1, champ par champ.

    changements, erreurs = assembler_tous(documents, changements_detectes)
    for changement in changements:
        suivi.traiter(changement)
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from leypilot.mesure.schemas import Changement, Dispositif, Evenement, IdentifiantsOfficiels
from leypilot.mesure.textes import normaliser


class TypeTexte(StrEnum):
    PROJET_LOI = "projet_loi"
    PROPOSITION_LOI = "proposition_loi"
    AMENDEMENT = "amendement"
    TEXTE_ADOPTE = "texte_adopte"
    LOI = "loi"
    ORDONNANCE = "ordonnance"
    DECRET = "decret"
    ARRETE = "arrete"
    DOCTRINE = "doctrine"  # BOFiP : cycle propre encore à définir (point ouvert)


ETAPE_PAR_TYPE: dict[TypeTexte, Evenement] = {
    TypeTexte.PROJET_LOI: Evenement.DEPOT,
    TypeTexte.PROPOSITION_LOI: Evenement.DEPOT,
    TypeTexte.AMENDEMENT: Evenement.DEPOT,
    TypeTexte.TEXTE_ADOPTE: Evenement.ADOPTION,
    TypeTexte.LOI: Evenement.PUBLICATION,
    TypeTexte.ORDONNANCE: Evenement.PUBLICATION,
    TypeTexte.DECRET: Evenement.PUBLICATION,
    TypeTexte.ARRETE: Evenement.PUBLICATION,
    TypeTexte.DOCTRINE: Evenement.PUBLICATION,
}

# Article de référence de chaque dispositif, quand le changement ne le précise pas.
ARTICLE_CGI: dict[Dispositif, str] = {
    Dispositif.CIR: "article 244 quater B du code général des impôts",
    Dispositif.CII: "article 244 quater B du code général des impôts",
    Dispositif.JEI: "article 44 sexies-0 A du code général des impôts",
}

# Article d'un code (« article 244 quater B du code général des impôts »). Un article
# sans code (« article 27 ») désigne l'article de la loi elle-même : il est ignoré.
_SUFFIXES = "bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies"
_ARTICLE_DE_CODE = re.compile(
    rf"\barticle\s+\d+(?:-\d+)?(?:\s+(?:{_SUFFIXES})(?:-\d+)?)?(?:\s+[A-Z]\b)?"
    r"\s+(?:du|de la)\s+(?:code général des impôts|CGI|livre des procédures fiscales)",
    re.IGNORECASE,
)


class DocumentFiltre(BaseModel):
    """Document retenu par le filtre de périmètre (S1 + S2, lot 1)."""

    model_config = ConfigDict(frozen=True)

    identifiant: int
    source: str = Field(min_length=1)  # legifrance, assemblee, senat, bofip
    type_texte: TypeTexte
    date_document: date
    texte: str = Field(min_length=1)
    identifiants: IdentifiantsOfficiels = Field(default_factory=IdentifiantsOfficiels)
    # Étape explicite quand le type de texte ne suffit pas : amendement rejeté ou
    # supprimé, censure du Conseil constitutionnel.
    etape: Evenement | None = None

    def evenement(self) -> Evenement:
        etape = self.etape or ETAPE_PAR_TYPE[self.type_texte]
        # Un amendement adopté n'est pas un texte voté : la mesure reste proposée.
        if self.type_texte == TypeTexte.AMENDEMENT and etape == Evenement.ADOPTION:
            return Evenement.ADOPTION_AMENDEMENT
        return etape


class ChangementDetecte(BaseModel):
    """Changement extrait par S2 (lot 1)."""

    model_config = ConfigDict(frozen=True)

    identifiant: int
    document_id: int
    dispositif: Dispositif
    parametre: str = Field(min_length=1)  # taux, plafond, date, condition
    ancienne_valeur: str | None = None
    nouvelle_valeur: str | None = None
    passage_cite: str = Field(min_length=1)
    article_vise: str | None = None  # facultatif : déduit du texte sinon
    conditions: tuple[str, ...] = ()  # conditions d'application lues dans le texte
    a_revoir: bool = False


class DocumentManquant(LookupError):
    pass


def deduire_article(dispositif: Dispositif, *zones: str) -> str:
    """Premier article cité dans le passage ou le texte, sinon l'article du dispositif."""
    for zone in zones:
        if trouve := _ARTICLE_DE_CODE.search(normaliser(zone)):
            return trouve.group(0)
    return ARTICLE_CGI[dispositif]


def assembler(changement: ChangementDetecte, document: DocumentFiltre) -> Changement:
    if changement.document_id != document.identifiant:
        raise DocumentManquant(
            f"Le changement {changement.identifiant} vient du document "
            f"{changement.document_id}, pas du document {document.identifiant}."
        )
    return Changement(
        identifiant=changement.identifiant,
        document_id=document.identifiant,
        evenement=document.evenement(),
        date_document=document.date_document,
        dispositif=changement.dispositif,
        article_vise=changement.article_vise
        or deduire_article(changement.dispositif, changement.passage_cite, document.texte),
        parametre=changement.parametre,
        ancienne_valeur=changement.ancienne_valeur,
        nouvelle_valeur=changement.nouvelle_valeur,
        passage_cite=changement.passage_cite,
        texte_source=document.texte,
        a_revoir=changement.a_revoir,
        identifiants=document.identifiants,
        conditions=changement.conditions,
    )


def assembler_tous(
    documents: Iterable[DocumentFiltre], changements: Iterable[ChangementDetecte]
) -> tuple[list[Changement], list[str]]:
    """Assemble chaque changement avec son document, dans l'ordre de la procédure.

    L'ordre (date du document, puis identifiant) garantit qu'un dépôt est traité
    avant l'adoption qui le suit. Un changement sans document est écarté et signalé.
    """
    par_id = {document.identifiant: document for document in documents}
    assembles: list[Changement] = []
    erreurs: list[str] = []
    for changement in changements:
        document = par_id.get(changement.document_id)
        if document is None:
            erreurs.append(
                f"Changement {changement.identifiant} : document {changement.document_id} "
                "introuvable, changement non traité."
            )
            continue
        assembles.append(assembler(changement, document))
    assembles.sort(key=lambda c: (c.date_document, c.identifiant))
    return assembles, erreurs
