from datetime import date

import pytest

from leypilot.commun.llm import ClientFactice, ClientNonConfigure, ServiceLLM
from leypilot.mesure.dates import chercher_clause, dater, jours_restants
from leypilot.mesure.schemas import NatureDate


@pytest.mark.parametrize(
    ("texte", "attendu", "type_clause"),
    [
        (
            "s'applique aux dépenses exposées à compter du 1er janvier 2026",
            date(2026, 1, 1),
            "depenses",
        ),
        (
            "pour les exercices clos à compter du 31 décembre 2025",
            date(2025, 12, 31),
            "exercices_clos",
        ),
        (
            "aux exercices ouverts à compter du 1er juillet 2026",
            date(2026, 7, 1),
            "exercices_ouverts",
        ),
        (
            "Le présent article entre en vigueur le 15 mars 2026.",
            date(2026, 3, 15),
            "entree_en_vigueur",
        ),
        ("Ces dispositions s'appliquent à partir du 01/09/2026.", date(2026, 9, 1), "a_compter_du"),
        ("a compter du 1er fevrier 2026", date(2026, 2, 1), "a_compter_du"),
    ],
)
def test_clauses_reconnues(texte, attendu, type_clause):
    trouvee = chercher_clause(texte)
    assert trouvee is not None
    assert (trouvee.date, trouvee.nature, trouvee.type_clause) == (
        attendu,
        NatureDate.CERTAINE,
        type_clause,
    )


def test_la_clause_la_plus_precise_l_emporte():
    texte = (
        "À compter du 1er janvier 2026, le taux est modifié. Ces dispositions s'appliquent aux "
        "dépenses exposées à compter du 1er juillet 2026."
    )
    trouvee = chercher_clause(texte)
    assert trouvee is not None
    assert trouvee.date == date(2026, 7, 1)


def test_date_impossible_ignoree():
    assert chercher_clause("à compter du 31 février 2026") is None


def test_lendemain_de_la_publication():
    trouvee = chercher_clause(
        "Le présent décret entre en vigueur le lendemain de sa publication.",
        date_publication=date(2026, 3, 10),
    )
    assert trouvee is not None
    assert trouvee.date == date(2026, 3, 11)
    assert trouvee.nature == NatureDate.CERTAINE


def test_clause_trouvee_dans_le_texte_complet(fabrique):
    changement = fabrique(passage_cite="le taux : « 30 % » est remplacé par le taux : « 20 % »")
    trouvee = dater(changement)
    assert trouvee is not None
    assert trouvee.date == date(2026, 1, 1)


def test_droit_commun_si_aucune_clause(fabrique):
    texte = "Au k du II de l'article 244 quater B du CGI, le taux de 30 % est remplacé par 20 %."
    changement = fabrique(texte_source=texte, passage_cite="le taux de 30 % est remplacé par 20 %")
    assert dater(changement) is None
    estimee = dater(changement, date_publication=date(2025, 12, 31))
    assert estimee is not None
    assert (estimee.date, estimee.nature, estimee.methode) == (
        date(2026, 1, 1),
        NatureDate.ESTIMEE,
        "droit_commun",
    )


def test_secours_llm_verifie_la_clause(fabrique):
    texte = (
        "Le taux de 30 % est remplacé par 20 %. Ces mesures valent pour les crédits calculés au "
        "titre des années 2026 et suivantes."
    )
    changement = fabrique(texte_source=texte, passage_cite="Le taux de 30 % est remplacé par 20 %")
    clause = "valent pour les crédits calculés au titre des années 2026 et suivantes"

    bonne = ServiceLLM(
        ClientFactice({"a4_date": [f'{{"clause": "{clause}", "date": "2026-01-01"}}']})
    )
    trouvee = dater(changement, service_llm=bonne)
    assert trouvee is not None
    assert (trouvee.date, trouvee.nature, trouvee.methode) == (
        date(2026, 1, 1),
        NatureDate.ESTIMEE,
        "llm",
    )

    inventee = ServiceLLM(
        ClientFactice(
            {"a4_date": ['{"clause": "clause inventée par le modèle", "date": "2026-01-01"}']}
        )
    )
    assert dater(changement, service_llm=inventee) is None


def test_secours_llm_absent_ne_bloque_pas(fabrique):
    changement = fabrique(
        texte_source="Le taux de 30 % est remplacé par 20 %.",
        passage_cite="Le taux de 30 % est remplacé par 20 %",
    )
    assert dater(changement, service_llm=ServiceLLM(ClientNonConfigure())) is None


def test_compte_a_rebours_six_semaines():
    assert jours_restants(date(2026, 1, 1), date(2025, 11, 20)) == 42
    assert jours_restants(date(2026, 1, 1), date(2026, 1, 5)) == -4
