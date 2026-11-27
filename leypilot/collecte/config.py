"""Réglages du lot 1, lus dans le ``.env`` (jamais dans le code ni dans Git)."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReglagesCollecte(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Compte PISTE (titulaire : P1). Le secret ne s'affiche jamais : SecretStr.
    piste_client_id: str = ""
    piste_client_secret: SecretStr = SecretStr("")

    # Fichiers bruts conservés tels que reçus (dossier ignoré par Git).
    dossier_donnees_brutes: Path = Path("donnees_brutes")


def reglages_collecte() -> ReglagesCollecte:
    return ReglagesCollecte()
