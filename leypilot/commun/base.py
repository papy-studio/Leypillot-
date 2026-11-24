"""Base déclarative SQLAlchemy commune à tous les lots.

Fichier du socle (P5) : toute table de Leypilot hérite de ``Base``.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def maintenant() -> datetime:
    """Horodatage en UTC, utilisé comme valeur par défaut des colonnes de date."""
    return datetime.now(UTC)
