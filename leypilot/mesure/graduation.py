"""A5 · Graduer : pas d'action sur une mesure qui n'est pas au moins votée.

La règle est garantie par la base : un trigger PostgreSQL sur la table
``action`` (propriété de P4) refuse toute action liée à une mesure proposée
ou abandonnée. ``verifier_action_autorisee`` donne la même règle côté Python,
pour un message clair avant d'écrire.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from sqlalchemy import Connection

from leypilot.mesure.schemas import StatutMesure

STATUTS_ACTIONNABLES = frozenset({StatutMesure.VOTEE, StatutMesure.PUBLIEE, StatutMesure.APPLIQUEE})

FICHIER_SQL = Path(__file__).parent / "sql" / "a5_action_mesure_votee.sql"
SEPARATEUR_SQL = "-- @@"


class Niveau(StrEnum):
    INFORMATION = "information"
    ACTION = "action"


class ActionInterdite(ValueError):
    pass


def niveau(statut: StatutMesure) -> Niveau:
    """Une mesure seulement déposée (ou abandonnée) produit une information, jamais une action."""
    return Niveau.ACTION if statut in STATUTS_ACTIONNABLES else Niveau.INFORMATION


def verifier_action_autorisee(statut: StatutMesure) -> None:
    if statut not in STATUTS_ACTIONNABLES:
        raise ActionInterdite(
            f"Action interdite sur une mesure au statut « {statut} » : "
            "elle doit être au moins votée."
        )


def instructions_sql() -> list[str]:
    """Instructions du fichier SQL, séparées par une ligne qui ne contient que ``-- @@``."""
    contenu = FICHIER_SQL.read_text(encoding="utf-8")
    blocs = re.split(rf"^{re.escape(SEPARATEUR_SQL)}\s*$", contenu, flags=re.MULTILINE)
    return [bloc.strip() for bloc in blocs if bloc.strip()]


def installer_contrainte_a5(connexion: Connection) -> None:
    """Installe le trigger (PostgreSQL uniquement). À appeler depuis la migration Alembic
    qui crée la table ``action``, une fois les tables ``mesure`` et ``action`` présentes."""
    if connexion.dialect.name != "postgresql":
        raise RuntimeError("La contrainte A5 est un trigger PostgreSQL.")
    # Curseur brut, sans paramètres : sinon psycopg lit les « % » du PL/pgSQL comme des
    # marqueurs de paramètres. La connexion reste celle de la transaction en cours.
    curseur = connexion.connection.cursor()
    try:
        for instruction in instructions_sql():
            curseur.execute(instruction)
    finally:
        curseur.close()
