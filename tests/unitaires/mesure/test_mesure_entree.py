"""Contrat d'entrée P1 → P2 : documents filtrés + changements détectés."""

from datetime import date

import pytest

from leypilot.mesure.entree import (
    ARTICLE_CGI,
    ChangementDetecte,
    DocumentFiltre,
    DocumentManquant,
    TypeTexte,
    assembler,
    assembler_tous,
    deduire_article,
)
from leypilot.mesure.schemas import Dispositif, Evenement

TEXTE = (
    "ARTICLE ADDITIONNEL APRÈS L'ARTICLE 12 : I. – Au k du II de l'article 244 quater B "
    "du code général des impôts, le taux : « 30 % » est remplacé par le taux : « 20 % »."
)


def document(**champs) -> DocumentFiltre:
    valeurs = {
        "identifiant": 10,
        "source": "assemblee",
        "type_texte": "amendement",
        "date_document": date(2025, 10, 28),
        "texte": TEXTE,
        "identifiants": {"dossier_legislatif": "PLF2026", "numero_amendement": "I-1234"},
    }
    valeurs.update(champs)
    return DocumentFiltre.model_validate(valeurs)


def detecte(**champs) -> ChangementDetecte:
    valeurs = {
        "identifiant": 1,
        "document_id": 10,
        "dispositif": "CII",
        "parametre": "taux",
        "ancienne_valeur": "30 %",
        "nouvelle_valeur": "20 %",
        "passage_cite": "le taux : « 30 % » est remplacé par le taux : « 20 % »",
    }
    valeurs.update(champs)
    return ChangementDetecte.model_validate(valeurs)


@pytest.mark.parametrize(
    ("type_texte", "etape"),
    [
        (TypeTexte.AMENDEMENT, Evenement.DEPOT),
        (TypeTexte.PROJET_LOI, Evenement.DEPOT),
        (TypeTexte.TEXTE_ADOPTE, Evenement.ADOPTION),
        (TypeTexte.LOI, Evenement.PUBLICATION),
        (TypeTexte.DECRET, Evenement.PUBLICATION),
    ],
)
def test_l_etape_vient_du_type_de_texte(type_texte, etape):
    assert document(type_texte=type_texte).evenement() == etape


def test_une_etape_explicite_l_emporte():
    assert document(etape="rejet").evenement() == Evenement.REJET


def test_assembler_reprend_le_texte_la_date_et_les_identifiants_du_document():
    changement = assembler(detecte(conditions=("PME",)), document())
    assert changement.evenement == Evenement.DEPOT
    assert changement.texte_source == TEXTE
    assert changement.date_document == date(2025, 10, 28)
    assert changement.identifiants.numero_amendement == "I-1234"
    assert changement.conditions == ("PME",)


def test_article_deduit_du_texte_et_pas_l_article_de_la_loi():
    changement = assembler(detecte(), document())
    assert changement.article_vise == "article 244 quater B du code général des impôts"


def test_article_fourni_par_le_lot_1_conserve():
    changement = assembler(detecte(article_vise="CGI, art. 244 quater B, II, k"), document())
    assert changement.article_vise == "CGI, art. 244 quater B, II, k"


def test_article_du_dispositif_quand_le_texte_n_en_cite_aucun():
    assert deduire_article(Dispositif.JEI, "aucun article", "rien") == ARTICLE_CGI[Dispositif.JEI]


def test_article_jei_deduit():
    texte = "L'article 44 sexies-0 A du code général des impôts est ainsi modifié."
    assert deduire_article(Dispositif.JEI, texte) == (
        "article 44 sexies-0 A du code général des impôts"
    )


def test_mauvais_document_refuse():
    with pytest.raises(DocumentManquant):
        assembler(detecte(document_id=99), document())


def test_assembler_tous_trie_par_date_et_signale_les_orphelins():
    adoption = document(identifiant=20, type_texte="texte_adopte", date_document=date(2025, 12, 18))
    changements, erreurs = assembler_tous(
        [adoption, document()],
        [
            detecte(identifiant=2, document_id=20),
            detecte(identifiant=1),
            detecte(identifiant=3, document_id=404),
        ],
    )
    assert [c.identifiant for c in changements] == [1, 2]
    assert [c.evenement for c in changements] == [Evenement.DEPOT, Evenement.ADOPTION]
    assert len(erreurs) == 1 and "404" in erreurs[0]
