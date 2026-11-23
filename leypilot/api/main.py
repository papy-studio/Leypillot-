"""Point d'entrée de l'API FastAPI."""

from fastapi import FastAPI

app = FastAPI(title="Leypilot", version="0.1.0")


@app.get("/sante")
def sante() -> dict[str, str]:
    """Vérifie que l'API répond."""
    return {"statut": "ok"}
