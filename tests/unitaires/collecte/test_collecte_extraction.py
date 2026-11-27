"""S2 : normalisation, formules législatives, format d'un changement."""

import pytest
from aide_collecte import CORPUS, lire_corpus
from pydantic import ValidationError

from leypilot.collecte.cibles import dans_perimetre
from leypilot.collecte.formules import extraire, tous_articles
from leypilot.collecte.schemas import (
    Changement,
    Methode,
    Motif,
    Passage,
    Statut,
    changements_du_texte,
    verifier_passage,
)
from leypilot.collecte.textes import empreinte_texte, normaliser, texte_brut

# ------------------------------------------------------------------ normalisation


def test_normaliser_espaces_apostrophes_et_i_point():
    brut = "İI. – L’article  244 quater B\n\n   est abrogé.  "
    assert normaliser(brut) == "II. – L'article 244 quater B\nest abrogé."


def test_normaliser_est_stable():
    texte = lire_corpus("lf2025.txt")
    assert normaliser(normaliser(texte)) == normaliser(texte)
    assert empreinte_texte(normaliser(texte)) == empreinte_texte(normaliser(normaliser(texte)))


def test_texte_brut_garde_les_paragraphes():
    assert texte_brut("<p>I. – A&nbsp;;</p><p>II. – B</p>") == "I. – A ;\nII. – B"


def test_filtre_large():
    assert dans_perimetre("Le crédit d’impôt recherche est prorogé")
    assert dans_perimetre(None, "article 44 sexies-0 A du code général des impôts")
    assert not dans_perimetre("Décret relatif aux horaires des bibliothèques")


# ------------------------------------------------------------------ formules


def _ops(nom: str):
    return [(op.operation, op.article, op.ancien, op.nouveau) for op in extraire(lire_corpus(nom))]


def test_fil_rouge_amendement_i_2211_sans_guillemet_fermant():
    (op,) = extraire(lire_corpus("an_I-2211.txt"))
    assert (op.operation, op.code, op.article) == (
        "remplacement",
        "code général des impôts",
        "244 quater B",
    )
    assert (op.ancien, op.nouveau) == ("30 %", "20 %")


def test_loi_de_finances_2025_article_56_et_sa_clause():
    ops = [op for op in extraire(lire_corpus("lf2025.txt")) if op.ancien == "30 %"]
    assert len(ops) == 1
    assert ops[0].localisation.startswith("À la fin de la quatrième phrase du premier alinéa du I")
    assert ops[0].clauses_application == [
        "II. – Le 1° du I s'applique aux dépenses exposées à compter du 1er janvier 2025."
    ]


@pytest.mark.parametrize(
    ("fichier", "attendu"),
    [
        ("jei_cf1411.txt", ("remplacement", "44 sexies-0 A", "onze", "huit")),
        ("senat_I-1179.txt", ("remplacement", "244 quater B", "30 %", "42 %")),
        ("senat_I-1521.txt", ("suppression_fin", "244 quater B", "30 %", None)),
        ("an_I-2942.txt", ("complement_imperatif", "244 quater B", None, None)),
        ("jei_415.txt", ("complement", "131", None, None)),
        ("an_2247_2562.txt", ("substitution_amendement", None, "II", "I")),
    ],
)
def test_une_formule_par_exemple_reel(fichier, attendu):
    assert attendu in _ops(fichier)


def test_le_nouveau_texte_entre_guillemets_n_est_pas_une_cible():
    phrase = "À l'article 13, les mots : « l'article 99 du code » sont remplacés par « x »."
    assert tous_articles(phrase) == [(None, "13")]


def test_la_lettre_d_article_respecte_la_casse():
    # Sans cela, « du » serait lu comme suffixe : « 244 quater B du » au lieu de « 244 quater B ».
    assert tous_articles("à l'article 244 quater B du code général des impôts") == [
        ("code général des impôts", "244 quater B")
    ]


# ------------------------------------------------------------------ changements


def test_tout_le_corpus_se_verifie_mot_pour_mot():
    total = 0
    for i, chemin in enumerate(sorted(CORPUS.glob("*.txt")), start=1):
        texte = normaliser(chemin.read_text(encoding="utf-8"))
        for changement in changements_du_texte(i, texte):
            assert verifier_passage(changement.passage, texte), chemin.name
            total += 1
    assert total >= 35


def test_rattachement_cii_par_la_subdivision():
    texte = normaliser(lire_corpus("lf2025.txt"))
    dispositifs = {
        (c.ancienne_valeur, c.localisation[:22]): c.dispositif
        for c in changements_du_texte(1, texte)
    }
    assert dispositifs[("30 %", "À la fin de la quatriè")] == "CII"  # quatrième phrase du I
    assert dispositifs[("2024", "Au premier alinéa du k")] == "CII"  # k du II (article 56)
    assert dispositifs[("2024", "Au premier alinéa du h")] == "CIR"  # h et i du II (article 57)
    assert dispositifs[("43 %", "II > c > au premier al")] == "CIR"


def test_un_texte_qui_touche_deux_dispositifs_donne_deux_changements():
    texte = normaliser(lire_corpus("lf2025.txt"))
    l80b = [c for c in changements_du_texte(1, texte) if c.article == "L. 80 B"]
    assert sorted(c.dispositif for c in l80b) == ["CIR", "JEI"]
    assert all(c.coordination for c in l80b)  # « la référence » : simple renvoi


def test_hors_cible_et_amendement_au_projet():
    texte = normaliser(lire_corpus("lf2025.txt"))
    hors = [c for c in changements_du_texte(1, texte) if c.article == "1653 F"]
    assert hors[0].statut == Statut.OK and hors[0].motifs == [Motif.HORS_CIBLE]
    (projet,) = changements_du_texte(2, normaliser(lire_corpus("an_2247_2562.txt")))
    assert projet.statut == Statut.A_REVOIR
    assert projet.motifs == [Motif.ALINEA_PROJET_NON_RESOLU]
    assert projet.alinea_projet == 3


def _changement(**champs) -> Changement:
    valeurs = {
        "document_id": 1,
        "operation": "remplacement",
        "article": "244 quater B",
        "dispositif": "CII",
        "ancienne_valeur": "30 %",
        "nouvelle_valeur": "20 %",
        "passage": Passage(
            document_id=1, debut=0, fin=10, texte="le taux : « 30 % » est remplacé par « 20 % »"
        ),
        "methode": Methode.REGEX,
        "statut": Statut.OK,
    }
    valeurs.update(champs)
    return Changement(**valeurs)


@pytest.mark.parametrize(
    ("champs", "message"),
    [
        ({"nouvelle_valeur": "25 %"}, "absente du passage"),
        ({"motifs": [Motif.ARTICLE_INCONNU]}, "ne peut pas avoir de motif"),
        ({"statut": Statut.A_REVOIR}, "doit dire pourquoi"),
        ({"methode": Methode.LLM}, "validation humaine"),
        ({"dispositif": None}, "sans dispositif"),
    ],
)
def test_validateurs_refusent_un_changement_incoherent(champs, message):
    with pytest.raises(ValidationError, match=message):
        _changement(**champs)


def test_validateurs_acceptent_le_cas_nominal():
    assert _changement().statut == Statut.OK
