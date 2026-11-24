"""Fixtures partagées par tous les lots."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import leypilot.commun.modeles  # noqa: F401  (enregistre toutes les tables)
from leypilot.commun.base import Base


@pytest.fixture
def session():
    """Base SQLite en mémoire, vide à chaque test."""
    moteur = create_engine("sqlite://")
    Base.metadata.create_all(moteur)
    with Session(moteur) as session:
        yield session
    moteur.dispose()
