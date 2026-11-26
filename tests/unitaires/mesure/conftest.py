"""Fixtures du lot 2."""

import json
from datetime import date
from pathlib import Path

import pytest

from leypilot.mesure.entree import ChangementDetecte, DocumentFiltre, assembler_tous
from leypilot.mesure.schemas import Changement

FICHIER_CLIENT_B = Path(__file__).parents[3] / "donnees_exemple" / "lot2_client_b.json"

TEXTE_TYPE = (
    "I. – Au premier alinéa du k du II de l'article 244 quater B du code général des impôts, "
    "le taux : « 30 % » est remplacé par le taux : « 20 % ». "
    "II. – Le I s'applique aux dépenses exposées à compter du 1er janvier 2026."
)


def changement(**champs) -> Changement:
    valeurs = {
        "identifiant": 1,
        "document_id": 10,
        "evenement": "depot",
        "date_document": date(2025, 10, 28),
        "dispositif": "CII",
        "article_vise": "article 244 quater B du code général des impôts",
        "parametre": "taux",
        "ancienne_valeur": "30 %",
        "nouvelle_valeur": "20 %",
        "passage_cite": "le taux : « 30 % » est remplacé par le taux : « 20 % »",
        "texte_source": TEXTE_TYPE,
    }
    valeurs.update(champs)
    return Changement.model_validate(valeurs)


@pytest.fixture
def fabrique():
    return changement


@pytest.fixture
def client_b() -> list[Changement]:
    donnees = json.loads(FICHIER_CLIENT_B.read_text(encoding="utf-8"))
    changements, erreurs = assembler_tous(
        [DocumentFiltre.model_validate(d) for d in donnees["documents"]],
        [ChangementDetecte.model_validate(c) for c in donnees["changements"]],
    )
    assert not erreurs
    return changements
