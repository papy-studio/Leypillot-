"""Prompts versionnés.

Chaque prompt est un fichier ``prompts/<nom>.<version>.toml`` avec deux champs :
``systeme`` (la consigne) et ``message`` (le gabarit, avec des variables ``$nom``).
On ne modifie jamais un fichier existant : on crée la version suivante et on
met à jour ``VERSIONS_ACTIVES``. La version fait partie de la clé du cache.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Template

from leypilot.commun.llm.client import RequeteLLM

DOSSIER_PROMPTS = Path(__file__).parent / "prompts"

VERSIONS_ACTIVES: dict[str, str] = {
    "s3_citation": "v1",
    "s3_resume": "v1",
    "a4_date": "v1",
}


@dataclass(frozen=True)
class Prompt:
    nom: str
    version: str
    systeme: str
    message: str
    max_jetons: int = 1024

    @property
    def identifiant(self) -> str:
        return f"{self.nom}.{self.version}"

    def requete(self, **valeurs: object) -> RequeteLLM:
        """Remplit le gabarit. Une valeur ``None`` devient « non précisé »."""
        textes = {cle: "non précisé" if v is None else str(v) for cle, v in valeurs.items()}
        try:
            message = Template(self.message).substitute(textes)
        except KeyError as manquante:
            raise ValueError(
                f"Valeur manquante {manquante} pour le prompt {self.identifiant}."
            ) from None
        return RequeteLLM(
            tache=self.nom,
            version_prompt=self.version,
            systeme=self.systeme,
            message=message,
            max_jetons=self.max_jetons,
        )


@lru_cache
def charger_prompt(nom: str, version: str | None = None) -> Prompt:
    if version is None:
        if nom not in VERSIONS_ACTIVES:
            raise ValueError(f"Prompt inconnu : {nom!r}.")
        version = VERSIONS_ACTIVES[nom]
    chemin = DOSSIER_PROMPTS / f"{nom}.{version}.toml"
    if not chemin.is_file():
        raise ValueError(f"Fichier de prompt introuvable : {chemin.name}.")
    donnees = tomllib.loads(chemin.read_text(encoding="utf-8"))
    return Prompt(
        nom=nom,
        version=version,
        systeme=donnees["systeme"].strip(),
        message=donnees["message"].strip(),
        max_jetons=int(donnees.get("max_jetons", 1024)),
    )
