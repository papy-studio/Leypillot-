"""Types du lot 2 et contrat d'entrée avec le lot 1.

``Changement`` est le format qu'on reçoit de la personne 1 (S2). C'est un
contrat provisoire : à valider avec elle, champ par champ.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Dispositif(StrEnum):
    CIR = "CIR"
    CII = "CII"
    JEI = "JEI"


class StatutMesure(StrEnum):
    PROPOSEE = "proposee"
    VOTEE = "votee"
    PUBLIEE = "publiee"
    APPLIQUEE = "appliquee"
    ABANDONNEE = "abandonnee"


class Evenement(StrEnum):
    """Étape de procédure portée par le document source."""

    DEPOT = "depot"  # amendement ou projet de texte déposé
    ADOPTION = "adoption"  # texte voté
    PUBLICATION = "publication"  # loi, décret ou arrêté publié au JO
    ENTREE_EN_VIGUEUR = "entree_en_vigueur"  # date d'application atteinte (tâche du lot 2)
    REJET = "rejet"
    SUPPRESSION = "suppression"
    CENSURE = "censure"


class NatureDate(StrEnum):
    CERTAINE = "certaine"  # lue dans le texte
    ESTIMEE = "estimee"  # déduite


class IdentifiantsOfficiels(BaseModel):
    model_config = ConfigDict(frozen=True)

    dossier_legislatif: str | None = None
    numero_amendement: str | None = None
    nor: str | None = None
    eli: str | None = None

    def identifiants_texte(self) -> dict[str, str]:
        """Identifiants d'un texte entier (un texte peut porter plusieurs mesures)."""
        return {
            cle: valeur
            for cle, valeur in (
                ("dossier_legislatif", self.dossier_legislatif),
                ("nor", self.nor),
                ("eli", self.eli),
            )
            if valeur
        }


class Changement(BaseModel):
    """Changement extrait par S2 (lot 1), entrée du lot 2."""

    model_config = ConfigDict(frozen=True)

    identifiant: int
    document_id: int
    evenement: Evenement
    date_document: date
    dispositif: Dispositif
    article_vise: str = Field(min_length=1)
    parametre: str = Field(min_length=1)
    ancienne_valeur: str | None = None
    nouvelle_valeur: str | None = None
    passage_cite: str = Field(min_length=1)
    texte_source: str = Field(min_length=1)
    a_revoir: bool = False
    identifiants: IdentifiantsOfficiels = Field(default_factory=IdentifiantsOfficiels)

    def empreinte_texte(self) -> str:
        return hashlib.sha256(self.texte_source.encode("utf-8")).hexdigest()

    def empreinte_changement(self) -> str:
        contenu = json.dumps(
            [
                self.evenement,  # le résumé mentionne l'étape de procédure
                self.dispositif,
                self.article_vise,
                self.parametre,
                self.ancienne_valeur,
                self.nouvelle_valeur,
                self.passage_cite,
            ],
            ensure_ascii=False,
        )
        return hashlib.sha256(contenu.encode("utf-8")).hexdigest()
