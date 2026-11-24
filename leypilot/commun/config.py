"""Configuration lue depuis les variables d'environnement (fichier .env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://leypilot:leypilot@localhost:5432/leypilot"

    # Couche LLM (P2). Fournisseur vide = pas de LLM : le lot 2 utilise ses gabarits.
    llm_fournisseur: str = ""
    llm_modele: str = ""
    llm_cle_api: str = ""

    jwt_secret: str = ""
    jwt_duree_minutes: int = 60


reglages = Reglages()
