"""Configuration lue depuis les variables d'environnement (fichier .env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://leypilot:leypilot@localhost:5432/leypilot"
    mistral_api_key: str = ""
    anthropic_api_key: str = ""
    jwt_secret: str = ""
    jwt_duree_minutes: int = 60


reglages = Reglages()
