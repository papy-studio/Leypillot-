"""Format d'un changement extrait par le lot 1 (S2), avec ses règles de validation.

Un changement = une opération sur un article, rattachée (ou non) à un dispositif, avec
le passage exact qui la prouve. Les validateurs refusent tout changement dont une
valeur n'est pas recopiée mot pour mot du passage.

La conversion vers le format d'entrée du lot 2 est dans ``vers_lot2.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from leypilot.collecte.cibles import rattacher
from leypilot.collecte.formules import Operation as OperationExtraite


class Operation(StrEnum):
    REMPLACEMENT = "remplacement"
    INSERTION_MOTS = "insertion_mots"
    SUPPRESSION_FIN = "suppression_fin"
    SUPPRESSION_MOTS = "suppression_mots"
    SUPPRESSION = "suppression"
    ABROGATION = "abrogation"
    INSERTION_SUBDIVISION = "insertion_subdivision"
    COMPLEMENT = "complement"
    COMPLEMENT_IMPERATIF = "complement_imperatif"
    REDACTION = "redaction"
    SUBSTITUTION_AMENDEMENT = "substitution_amendement"
    CREATION_ARTICLE = "creation_article"  # vu dans LEGI : nouvel article
    ABROGATION_ARTICLE = "abrogation_article"  # vu dans LEGI : article abrogé


class Methode(StrEnum):
    REGEX = "regex"  # formules législatives
    LEGI = "legi"  # comparaison de deux versions LEGI
    LLM = "llm"  # extraction de secours


class Statut(StrEnum):
    OK = "ok"
    A_REVOIR = "a_revoir"


class Motif(StrEnum):
    ARTICLE_INCONNU = "article_inconnu"  # aucun article, ni dans la phrase ni dans les chapeaux
    HORS_CIBLE = "hors_cible"  # article absent de la table cible : information, pas un défaut
    AUCUNE_FORMULE = "aucune_formule"  # phrase qui cite un article suivi, sans formule reconnue
    PASSAGE_INTROUVABLE = "passage_introuvable"  # vérification mot pour mot échouée
    VALEURS_AMBIGUES = "valeurs_ambigues"  # plusieurs valeurs possibles dans la même phrase
    REGLE_SUBDIVISION_EXPIREE = "regle_subdivision_expiree"  # article réécrit depuis la règle
    DESACCORD_LEGI = "desaccord_legi"  # le JO et la nouvelle version LEGI divergent
    ALINEA_PROJET_NON_RESOLU = (
        "alinea_projet_non_resolu"  # amendement au projet : article à retrouver
    )
    EXTRACTION_LLM = "extraction_llm"  # trouvé par le LLM de secours


class Passage(BaseModel):
    """Position du passage dans ``document.texte`` (texte normalisé)."""

    model_config = ConfigDict(frozen=True)

    document_id: int
    debut: int = Field(ge=0)
    fin: int = Field(ge=0)
    texte: str = Field(min_length=1)


class Changement(BaseModel):
    """Changement extrait (table ``changement``, propriétaire P1)."""

    document_id: int
    operation: Operation
    code: str | None = None  # « code général des impôts », « loi n° 2003-1311 »…
    article: str | None = None  # « 244 quater B »
    localisation: str = ""  # « I > quatrième phrase du premier alinéa »
    dispositif: str | None = None  # CIR, CII, JEI
    parametre: str | None = None  # nom du paramètre fixé par la personne 3, si connu
    objet: str | None = None  # « le taux », « l'année », « les mots »…
    ancienne_valeur: str | None = None
    nouvelle_valeur: str | None = None
    passage: Passage
    methode: Methode
    coordination: bool = False  # simple mise à jour d'un renvoi (« la référence »)
    alinea_projet: int | None = None  # amendement au projet de loi : alinéa visé
    clauses_application: list[str] = Field(default_factory=list)  # recopiées telles quelles
    statut: Statut
    motifs: list[Motif] = Field(default_factory=list)
    cree_le: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def coherence(self) -> Changement:
        # 1. Les valeurs sont recopiées mot pour mot du passage.
        for nom in ("ancienne_valeur", "nouvelle_valeur"):
            valeur = getattr(self, nom)
            if valeur and valeur not in self.passage.texte:
                raise ValueError(f"{nom} absente du passage : {valeur!r}")
        # 2. Statut et motifs vont ensemble (« hors_cible » n'est qu'une information).
        bloquants = [m for m in self.motifs if m != Motif.HORS_CIBLE]
        if self.statut == Statut.OK and bloquants:
            raise ValueError("un changement « ok » ne peut pas avoir de motif « à revoir »")
        if self.statut == Statut.A_REVOIR and not bloquants:
            raise ValueError("un changement « à revoir » doit dire pourquoi")
        # 3. Le LLM de secours ne produit jamais un changement « ok » dans le MVP.
        if self.methode == Methode.LLM and self.statut == Statut.OK:
            raise ValueError("une extraction par LLM reste « à revoir » jusqu'à validation humaine")
        # 4. Un changement « ok » dans le périmètre est rattaché à un dispositif.
        if self.statut == Statut.OK and not self.dispositif and Motif.HORS_CIBLE not in self.motifs:
            raise ValueError("changement « ok » sans dispositif")
        return self


def verifier_passage(passage: Passage, texte_document: str) -> bool:
    """Vérification mot pour mot : la position désigne exactement le texte cité."""
    return texte_document[passage.debut : passage.fin] == passage.texte


def dispositifs_de(operation: OperationExtraite) -> list[str]:
    if not operation.article:
        return []
    articles = operation.articles or [(operation.code, operation.article)]
    return rattacher(articles, operation.localisation, operation.passage)


def depuis_operation(
    operation: OperationExtraite,
    document_id: int,
    texte_document: str,
    dispositif: str | None = None,
) -> Changement:
    """Transforme une opération de ``formules.extraire`` en ``Changement`` validé.

    ``texte_document`` est ``document.texte`` (déjà normalisé). Un texte qui touche deux
    dispositifs donne un changement par dispositif : passer ``dispositif`` à chaque appel.
    """
    debut = texte_document.find(operation.passage)
    motifs: list[Motif] = []
    if debut < 0:
        motifs.append(Motif.PASSAGE_INTROUVABLE)
        debut = 0
    passage = Passage(
        document_id=document_id,
        debut=debut,
        fin=debut + len(operation.passage),
        texte=operation.passage,
    )
    dispositifs = dispositifs_de(operation)
    if operation.operation == Operation.SUBSTITUTION_AMENDEMENT:
        motifs.append(Motif.ALINEA_PROJET_NON_RESOLU)
    elif not operation.article:
        motifs.append(Motif.ARTICLE_INCONNU)
    elif not dispositifs:
        motifs.append(Motif.HORS_CIBLE)
    if any(clause not in texte_document for clause in operation.clauses_application):
        motifs.append(Motif.PASSAGE_INTROUVABLE)
    bloquant = any(m != Motif.HORS_CIBLE for m in motifs)
    return Changement(
        document_id=document_id,
        operation=Operation(operation.operation),
        code=operation.code,
        article=operation.article,
        localisation=operation.localisation,
        dispositif=dispositif or (dispositifs[0] if dispositifs else None),
        objet=operation.objet,
        ancienne_valeur=operation.ancien,
        nouvelle_valeur=operation.nouveau,
        passage=passage,
        methode=Methode.REGEX,
        coordination=(operation.objet or "").lower() == "la référence",
        alinea_projet=operation.alinea_projet,
        clauses_application=operation.clauses_application,
        statut=Statut.A_REVOIR if bloquant else Statut.OK,
        motifs=motifs,
    )


def changements_du_texte(document_id: int, texte_document: str) -> list[Changement]:
    """Tous les changements d'un document : un par opération et par dispositif touché."""
    from leypilot.collecte.formules import extraire

    resultat: list[Changement] = []
    for operation in extraire(texte_document):
        dispositifs = dispositifs_de(operation)
        for dispositif in dispositifs if len(dispositifs) > 1 else [None]:
            resultat.append(depuis_operation(operation, document_id, texte_document, dispositif))
    return resultat
