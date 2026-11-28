from datetime import date

import pytest

from leypilot.mesure.controle_dates import erreurs_de_date, extraire_dates
from leypilot.mesure.dates import DateVigueur
from leypilot.mesure.schemas import NatureDate

JANVIER = date(2026, 1, 1)
CERTAINE = DateVigueur(JANVIER, NatureDate.CERTAINE, None, "depenses", "regex")
ESTIMEE = DateVigueur(JANVIER, NatureDate.ESTIMEE, None, "droit_commun", "droit_commun")
CITATION = "le taux : « 30 % » est remplacé par le taux : « 20 % »"


@pytest.mark.parametrize(
    "ecrit",
    ["1er janvier 2026", "1ᵉʳ janvier 2026", "1 janvier 2026", "01/01/2026", "2026-01-01"],
)
def test_formats_de_date_reconnus(ecrit):
    assert extraire_dates(f"Applicable au {ecrit}.") == {JANVIER}


def test_mois_accentues_et_dates_impossibles():
    assert extraire_dates("le 15 février 2026 et le 31/02/2026") == {date(2026, 2, 15)}


def test_resume_correct():
    texte = "Le taux du CII passe de 30 % à 20 % à compter du 1er janvier 2026."
    assert erreurs_de_date(texte, CITATION, CERTAINE) == []


@pytest.mark.parametrize(
    "texte",
    [
        # Réponses réelles de gpt-oss-120b avec le prompt v1.
        "S'applique à compter du 1er janvier 2026. Elle entre en vigueur dès la publication "
        "du texte au Journal officiel.",
        "Cette modification s'applique dès le 1er janvier 2026, dès que la mesure est votée.",
        "Cette modification est effective dès la publication au Journal officiel et s'applique "
        "à compter du 1er janvier 2026.",
        # Autres tournures.
        "Applicable au 1er janvier 2026, après son adoption.",
        "Le 1er janvier 2026 ; la mesure prend effet à compter du vote.",
        "Au 1er janvier 2026, dès qu'elle sera promulguée.",
    ],
)
def test_application_rattachee_a_une_etape(texte):
    [erreur] = erreurs_de_date(texte, CITATION, CERTAINE)
    assert "étape de la procédure" in erreur


def test_etape_mentionnee_sans_lien_avec_l_application():
    texte = (
        "Le texte a été publié au Journal officiel. Le taux passe à 20 % "
        "à compter du 1er janvier 2026."
    )
    assert erreurs_de_date(texte, CITATION, CERTAINE) == []


def test_application_liee_a_la_publication_permise_si_le_texte_le_dit():
    texte = "Le taux passe à 20 %. Applicable au 1er janvier 2026, dès la publication."
    citation = "entre en vigueur dès la publication de la présente loi"
    assert erreurs_de_date(texte, citation, CERTAINE) == []

    clause = "La présente loi entre en vigueur à compter de sa publication."
    avec_clause = DateVigueur(JANVIER, NatureDate.CERTAINE, clause, "loi", "regex")
    assert erreurs_de_date(texte, CITATION, avec_clause) == []


def test_date_d_application_absente():
    [erreur] = erreurs_de_date("Le taux passe à 20 %.", CITATION, CERTAINE)
    assert "1er janvier 2026" in erreur and "n'apparaît pas" in erreur


def test_date_inventee():
    texte = "Le taux passe à 20 % au 1er janvier 2026, puis au 1er juillet 2027."
    [erreur] = erreurs_de_date(texte, CITATION, CERTAINE)
    assert "1er juillet 2027" in erreur


def test_date_de_la_citation_autorisee():
    citation = (
        "pour les dépenses exposées à compter du 1er janvier 2026 et jusqu'au 31 décembre 2028"
    )
    texte = "Applicable du 1er janvier 2026 au 31 décembre 2028."
    assert erreurs_de_date(texte, citation, CERTAINE) == []


def test_date_estimee_presentee_comme_certaine():
    [erreur] = erreurs_de_date("Applicable au 1er janvier 2026.", CITATION, ESTIMEE)
    assert "estimée" in erreur
    assert (
        erreurs_de_date("Date estimée au 1er janvier 2026, à confirmer.", CITATION, ESTIMEE) == []
    )


def test_sans_date_connue_aucune_date_inventee():
    assert erreurs_de_date("Date d'application non précisée.", CITATION, None) == []
    [erreur] = erreurs_de_date("Applicable au 1er janvier 2026.", CITATION, None)
    assert "1er janvier 2026" in erreur


def test_le_gabarit_passe_toujours_le_controle(fabrique):
    from leypilot.mesure.resume import RedacteurGabarit

    gabarit = RedacteurGabarit()
    for evenement in ("depot", "adoption", "publication"):
        changement = fabrique(evenement=evenement)
        for date_vigueur in (CERTAINE, ESTIMEE, None):
            texte = gabarit.rediger(changement, CITATION, "", date_vigueur)
            assert erreurs_de_date(texte, CITATION, date_vigueur) == [], texte
