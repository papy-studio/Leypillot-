from decimal import Decimal

import pytest

from leypilot.commun.llm import (
    chiffres_en_dur,
    contient_montant,
    extraire_montants,
    montants_non_justifies,
)


@pytest.mark.parametrize(
    ("texte", "valeur"),
    [
        ("400 000 €", Decimal("400000")),
        ("400 000 euros", Decimal("400000")),
        ("400.000 EUR", Decimal("400000")),
        ("40 000€", Decimal("40000")),
        ("1,5 million d'euros", Decimal("1500000")),
        ("100 M€", Decimal("100000000")),
        ("2 Md€", Decimal("2000000000")),
        ("400 k€", Decimal("400000")),
        ("12,50 €", Decimal("12.5")),
    ],
)
def test_reconnait_les_montants(texte, valeur):
    montants = extraire_montants(f"Le plafond est de {texte} par an.")
    assert [m.valeur for m in montants] == [valeur.normalize()]


def test_ignore_taux_annees_et_articles():
    texte = "Le taux passe de 30 % à 20 % en 2026 (article 244 quater B, II, k)."
    assert extraire_montants(texte) == []
    assert not contient_montant(texte)


def test_ne_colle_pas_une_annee_a_un_montant():
    assert [m.valeur for m in extraire_montants("En 2025 400 000 € de dépenses.")] == [
        Decimal("400000")
    ]


def test_montant_present_dans_la_citation_est_autorise():
    citation = "dans la limite de 400 000 euros de dépenses"
    assert montants_non_justifies("Le plafond reste de 400 k€.", citation) == []


def test_montant_invente_est_signale():
    citation = "le taux : « 30 % » est remplacé par le taux : « 20 % »"
    sortie = "Pour une entreprise type, cela représente 40 000 € de moins."
    assert [m.brut for m in montants_non_justifies(sortie, citation)] == ["40 000 €"]


def test_chiffres_en_dur_hors_emplacements():
    assert chiffres_en_dur("{montant} en jeu, échéance dans {délai}") == []
    assert chiffres_en_dur("{montant} en jeu, échéance dans 6 semaines") == ["6"]
