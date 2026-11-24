from leypilot.mesure.rattachement import CandidatMesure, Methode, rattacher
from leypilot.mesure.schemas import Dispositif, IdentifiantsOfficiels, StatutMesure


def candidat(**champs) -> CandidatMesure:
    valeurs = {
        "id": 1,
        "dispositif": Dispositif.CII,
        "article_vise": "article 244 quater B du code général des impôts",
        "parametre": "taux du crédit d'impôt innovation",
        "statut": StatutMesure.PROPOSEE,
        "identifiants": IdentifiantsOfficiels(dossier_legislatif="PLF2026"),
        "numeros_amendement": frozenset({"I-1234"}),
    }
    valeurs.update(champs)
    return CandidatMesure(**valeurs)


def test_meme_amendement(fabrique):
    changement = fabrique(identifiants={"numero_amendement": "I-1234"}, parametre="autre chose")
    decision = rattacher(changement, [candidat()])
    assert (decision.mesure_id, decision.methode, decision.a_valider) == (
        1,
        Methode.AMENDEMENT,
        False,
    )


def test_numerotation_differente_mais_meme_article(fabrique):
    changement = fabrique(article_vise="CGI, art. 244 quater B, II, k", parametre="taux")
    decision = rattacher(changement, [candidat()])
    assert decision.mesure_id == 1
    assert decision.methode == Methode.SIMILARITE
    assert not decision.a_valider


def test_autre_article_donne_une_nouvelle_mesure(fabrique):
    changement = fabrique(dispositif="JEI", article_vise="article 44 sexies-0 A du CGI")
    assert rattacher(changement, [candidat()]).nouvelle_mesure


def test_autre_dispositif_ou_mesure_terminee_exclus(fabrique):
    changement = fabrique()
    assert rattacher(changement, [candidat(dispositif=Dispositif.CIR)]).nouvelle_mesure
    assert rattacher(changement, [candidat(statut=StatutMesure.APPLIQUEE)]).nouvelle_mesure


def test_autre_dossier_legislatif_exclu(fabrique):
    changement = fabrique(identifiants={"dossier_legislatif": "PLF2027"})
    assert rattacher(changement, [candidat()]).nouvelle_mesure


def test_score_ambigu_soumis_a_un_humain(fabrique):
    changement = fabrique(parametre="plafond des dépenses de prototypes")
    decision = rattacher(changement, [candidat()], seuil_auto=95, seuil_humain=50)
    assert decision.mesure_id == 1
    assert decision.a_valider


def test_texte_commun_rend_le_rattachement_automatique(fabrique):
    changement = fabrique(
        parametre="plafond des dépenses de prototypes",
        identifiants={"dossier_legislatif": "PLF2026"},
    )
    decision = rattacher(changement, [candidat()], seuil_auto=95, seuil_humain=50)
    assert decision.mesure_id == 1
    assert not decision.a_valider


def test_le_meilleur_candidat_gagne(fabrique):
    changement = fabrique(parametre="taux")
    plafond = candidat(id=2, parametre="plafond de dépenses", numeros_amendement=frozenset())
    taux = candidat(id=3, parametre="taux", numeros_amendement=frozenset())
    assert rattacher(changement, [plafond, taux]).mesure_id == 3
