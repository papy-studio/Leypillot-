"""S3 · Résumer : un consultant comprend le changement sans ouvrir le texte.

Chaîne : contexte → citation (vérifiée mot pour mot) → rédaction → filtre
anti-montant → drapeau « à vérifier ».

Deux rédacteurs partagent la même interface :
- ``RedacteurGabarit`` : déterministe, sans LLM (utilisé par défaut) ;
- ``RedacteurLLM`` : deux appels au LLM (citation, puis résumé).
Sans LLM configuré, le gabarit est le rédacteur. Si le LLM échoue après ses
nouvelles tentatives, le gabarit fournit un texte provisoire et le résumé est
marqué « en attente » : il sera relancé plus tard (répartition, couche LLM).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, Field

from leypilot.commun.llm import VERSIONS_ACTIVES, ErreurLLM, ServiceLLM, montants_non_justifies
from leypilot.mesure.contexte import ContexteVide, SourceContexte, construire_contexte
from leypilot.mesure.dates import DateVigueur
from leypilot.mesure.drapeaux import MOTIF_CITATION, MOTIF_MONTANT, detecter_doutes
from leypilot.mesure.schemas import Changement, Evenement, NatureDate
from leypilot.mesure.textes import citation_verifiee, date_en_francais

journal = logging.getLogger(__name__)

VERSION_GABARIT = "gabarit.v1"

LIBELLES_ETAPE = {
    Evenement.DEPOT: "mesure proposée (amendement ou projet de texte déposé)",
    Evenement.ADOPTION: "mesure votée",
    Evenement.ADOPTION_AMENDEMENT: "amendement adopté en séance, texte pas encore voté",
    Evenement.PUBLICATION: "texte publié au Journal officiel",
    Evenement.ENTREE_EN_VIGUEUR: "mesure entrée en application",
    Evenement.REJET: "mesure rejetée",
    Evenement.SUPPRESSION: "mesure supprimée",
    Evenement.CENSURE: "mesure censurée par le Conseil constitutionnel",
}


def phrase_date(date_vigueur: DateVigueur | None) -> str:
    if date_vigueur is None:
        return "Date d'application non précisée par le texte."
    jour = date_en_francais(date_vigueur.date)
    if date_vigueur.nature == NatureDate.CERTAINE:
        return f"Applicable à compter du {jour}."
    return f"Date d'application estimée au {jour}, à confirmer."


class Redacteur(Protocol):
    methode: str
    version: str

    def citer(self, changement: Changement, contexte: str) -> str: ...

    def rediger(
        self,
        changement: Changement,
        citation: str,
        contexte: str,
        date_vigueur: DateVigueur | None,
        *,
        regeneration: bool = False,
    ) -> str: ...


class RedacteurGabarit:
    methode = "gabarit"
    version = VERSION_GABARIT

    def citer(self, changement: Changement, contexte: str) -> str:
        return changement.passage_cite

    def rediger(
        self,
        changement: Changement,
        citation: str,
        contexte: str,
        date_vigueur: DateVigueur | None,
        *,
        regeneration: bool = False,
    ) -> str:
        quoi = f"« {changement.parametre} »"
        ancienne, nouvelle = changement.ancienne_valeur, changement.nouvelle_valeur
        if ancienne and nouvelle:
            phrase = f"{quoi} passe de {ancienne} à {nouvelle}"
        elif nouvelle:
            phrase = f"{quoi} est désormais : {nouvelle}"
        elif ancienne:
            phrase = f"{quoi} ({ancienne}) est supprimé"
        else:
            phrase = f"{quoi} est modifié"
        return " ".join(
            [
                f"{changement.dispositif} : {phrase} ({changement.article_vise}).",
                f"Étape : {LIBELLES_ETAPE[changement.evenement]}.",
                phrase_date(date_vigueur),
            ]
        )


class CitationLLM(BaseModel):
    citation: str = Field(min_length=1)


class ResumeLLM(BaseModel):
    resume: str = Field(min_length=1)


class RedacteurLLM:
    methode = "llm"

    def __init__(self, service: ServiceLLM) -> None:
        self.service = service
        citation, resume = VERSIONS_ACTIVES["s3_citation"], VERSIONS_ACTIVES["s3_resume"]
        self.version = f"s3_citation.{citation}+s3_resume.{resume}"

    def _champs(self, changement: Changement) -> dict[str, object]:
        # Uniquement des données publiques : aucune donnée client n'entre dans un prompt.
        return {
            "dispositif": changement.dispositif,
            "article_vise": changement.article_vise,
            "parametre": changement.parametre,
            "ancienne_valeur": changement.ancienne_valeur,
            "nouvelle_valeur": changement.nouvelle_valeur,
        }

    def citer(self, changement: Changement, contexte: str) -> str:
        valeurs = {"texte": changement.texte_source, **self._champs(changement)}
        return self.service.generer("s3_citation", CitationLLM, valeurs).citation

    def rediger(
        self,
        changement: Changement,
        citation: str,
        contexte: str,
        date_vigueur: DateVigueur | None,
        *,
        regeneration: bool = False,
    ) -> str:
        valeurs = {
            "citation": citation,
            "contexte": contexte,
            "etape": LIBELLES_ETAPE[changement.evenement],
            "date_application": phrase_date(date_vigueur),
            **self._champs(changement),
        }
        return self.service.generer("s3_resume", ResumeLLM, valeurs, forcer=regeneration).resume


@dataclass
class ResumeProduit:
    texte: str
    citation: str
    methode: str
    version: str
    motifs: list[str] = field(default_factory=list)
    en_attente: bool = False  # LLM en échec : texte provisoire du gabarit, à relancer

    @property
    def a_verifier(self) -> bool:
        return bool(self.motifs)


class ResumeurS3:
    def __init__(
        self,
        redacteur: Redacteur | None = None,
        source_contexte: SourceContexte | None = None,
        lexique: frozenset[str] = frozenset(),
    ) -> None:
        self.redacteur: Redacteur = redacteur or RedacteurGabarit()
        self.secours = RedacteurGabarit()
        self.source_contexte = source_contexte or ContexteVide()
        self.lexique = lexique

    @property
    def version(self) -> str:
        return self.redacteur.version

    def resumer(
        self, changement: Changement, date_vigueur: DateVigueur | None = None
    ) -> ResumeProduit:
        contexte = construire_contexte(self.source_contexte, changement)
        motifs = detecter_doutes(changement, self.lexique)
        try:
            return self._produire(self.redacteur, changement, contexte, date_vigueur, motifs)
        except ErreurLLM as erreur:
            journal.warning("S3 : LLM en échec (%s), résumé provisoire en attente.", erreur)
            provisoire = self._produire(self.secours, changement, contexte, date_vigueur, motifs)
            provisoire.en_attente = True
            return provisoire

    def _produire(
        self,
        redacteur: Redacteur,
        changement: Changement,
        contexte: str,
        date_vigueur: DateVigueur | None,
        motifs_initiaux: list[str],
    ) -> ResumeProduit:
        motifs = list(motifs_initiaux)
        citation = self._citation(redacteur, changement, contexte, motifs)

        texte = redacteur.rediger(changement, citation, contexte, date_vigueur)
        if montants_non_justifies(texte, citation):
            journal.warning("S3 : montant hors citation, régénération (%s).", redacteur.methode)
            texte = redacteur.rediger(
                changement, citation, contexte, date_vigueur, regeneration=True
            )
        if montants_non_justifies(texte, citation) and redacteur is not self.secours:
            journal.warning("S3 : montant hors citation après régénération, gabarit.")
            redacteur = self.secours
            texte = redacteur.rediger(changement, citation, contexte, date_vigueur)
        if montants_non_justifies(texte, citation):
            motifs.append(MOTIF_MONTANT)

        return ResumeProduit(texte, citation, redacteur.methode, redacteur.version, motifs)

    def _citation(
        self, redacteur: Redacteur, changement: Changement, contexte: str, motifs: list[str]
    ) -> str:
        citation = redacteur.citer(changement, contexte)
        if citation_verifiee(citation, changement.texte_source):
            return citation
        if citation != changement.passage_cite:
            journal.warning(
                "S3 : citation du LLM introuvable dans le texte, passage de S2 utilisé."
            )
        if not citation_verifiee(changement.passage_cite, changement.texte_source):
            motifs.append(MOTIF_CITATION)
        return changement.passage_cite


def creer_resumeur(
    service_llm: ServiceLLM | None = None,
    source_contexte: SourceContexte | None = None,
    lexique: frozenset[str] = frozenset(),
) -> ResumeurS3:
    """Résumeur LLM si un service est fourni, gabarit sinon."""
    redacteur = RedacteurLLM(service_llm) if service_llm is not None else RedacteurGabarit()
    return ResumeurS3(redacteur, source_contexte, lexique)
