"""Comparaison LEGI (deuxième regard sur le JO) et extraction de secours par LLM."""

import json

from aide_collecte import LOI, PHRASE_CII, article_legi, fabriquer_archive_legi, lire_corpus
from sqlalchemy import select

from leypilot.collecte import depot, vers_lot2
from leypilot.collecte.comparaison_legi import comparer
from leypilot.collecte.formules import extraire_tout
from leypilot.collecte.schemas import Methode, Motif, Operation, Statut, changements_du_texte
from leypilot.collecte.sources import jorf, legi
from leypilot.collecte.textes import normaliser
from leypilot.commun.llm import ClientFactice, ClientNonConfigure, ServiceLLM
from leypilot.commun.modeles.collecte import ChangementExtrait, Document

CGI = "code général des impôts"

# ------------------------------------------------------------------ LEGI


def test_legi_garde_la_version_actuelle_des_articles_suivis(tmp_path):
    chemin = fabriquer_archive_legi(
        tmp_path,
        "LEGI_20250216-003012.tar.gz",
        [
            article_legi("LEGIARTI1", "244 quater B", "MODIFIE", "2024-01-01", "ancienne"),
            article_legi("LEGIARTI2", "244 quater B", "VIGUEUR", "2025-02-16", "en vigueur"),
            article_legi("LEGIARTI3", "244 quater B", "VIGUEUR_DIFF", "2026-01-01", "à venir"),
            article_legi("LEGIARTI4", "278 bis", "VIGUEUR", "2025-02-16", "hors cible"),
        ],
    )
    collecte = legi.lire_archive(chemin)
    (document,) = collecte.documents
    assert document.identifiant == f"{CGI}/244 quater B"
    assert document.texte == "à venir" and document.meta["legiarti"] == "LEGIARTI3"


def test_un_montant_reste_entier():
    (changement,) = comparer(
        2,
        CGI,
        "244 quater B",
        "plafond de 400 000 € par an.",
        "plafond de 500 000 € par an.",
        "VIGUEUR",
    )
    assert (changement.ancienne_valeur, changement.nouvelle_valeur) == ("400 000 €", "500 000 €")


def test_comparer_trouve_le_remplacement_et_le_dispositif():
    avant = PHRASE_CII.format(taux="30 %")
    apres = PHRASE_CII.format(taux="20 %")
    (changement,) = comparer(2, CGI, "244 quater B", avant, apres, "VIGUEUR", 1)
    assert (changement.operation, changement.methode) == (Operation.REMPLACEMENT, Methode.LEGI)
    assert (changement.ancienne_valeur, changement.nouvelle_valeur) == ("30 %", "20 %")
    assert changement.dispositif == "CII"  # « k du II » dans la phrase
    assert changement.passage.texte.startswith("Le taux du crédit d'impôt est porté à 20 %")
    assert changement.passage_precedent.document_id == 1
    assert comparer(2, CGI, "244 quater B", None, apres, "VIGUEUR") == []  # référence


def test_comparer_abrogation():
    (changement,) = comparer(
        3, CGI, "44 sexies A", "texte", "Article 44 sexies A (abroge)", "ABROGE"
    )
    assert changement.operation == Operation.ABROGATION_ARTICLE
    assert changement.dispositif == "JEI"


def _versions(session, tmp_path, archive_jorf, taux_final):
    depot.enregistrer_collecte(session, jorf.lire_fichier(archive_jorf))
    for i, (taux, modificateur) in enumerate((("30 %", None), (taux_final, LOI))):
        chemin = fabriquer_archive_legi(
            tmp_path,
            f"LEGI_2025021{i}-003012.tar.gz",
            [
                article_legi(
                    f"LEGIARTI{i}",
                    "244 quater B",
                    "VIGUEUR",
                    f"2025-02-1{i}",
                    PHRASE_CII.format(taux=taux),
                    modificateur,
                )
            ],
        )
        depot.enregistrer_collecte(session, legi.lire_archive(chemin))
    return session.scalars(
        select(ChangementExtrait).join(Document).where(Document.source == "LEGI")
    ).all()


def test_legi_confirme_le_jo(session, tmp_path, archive_jorf):
    (changement,) = _versions(session, tmp_path, archive_jorf, "20 %")
    assert (changement.ancienne_valeur, changement.nouvelle_valeur) == ("30 %", "20 %")
    assert changement.statut == Statut.OK and changement.motifs == []
    assert changement.passage_precedent["texte"].startswith(
        "Le taux du crédit d'impôt est porté à 30 %"
    )


def test_legi_en_desaccord_avec_le_jo(session, tmp_path, archive_jorf):
    (changement,) = _versions(session, tmp_path, archive_jorf, "25 %")
    assert changement.statut == Statut.A_REVOIR
    assert changement.motifs == [Motif.DESACCORD_LEGI]
    # Les changements LEGI ne partent pas vers le lot 2.
    assert all(d["source"] != "LEGI" for d, _ in depot.pour_lot2(session))


# ------------------------------------------------------------------ secours


TEXTE_I_1521 = normaliser(lire_corpus("senat_I-1521.txt"))
LIGNE = (
    "II. – Le taux de 30 % mentionné à la deuxième phrase du I de l'article 244 quater B du code "
    "général des impôts est augmenté à due concurrence"
)


def test_une_ligne_sans_formule_est_reperee():
    _, lignes = extraire_tout(TEXTE_I_1521)
    (ligne,) = lignes
    assert ligne.ligne.startswith("II. – Le taux de 30 %") and ligne.article == "244 quater B"


def _secours(service=None):
    return [
        c
        for c in changements_du_texte(1, TEXTE_I_1521, service)
        if Motif.AUCUNE_FORMULE in c.motifs
    ]


def test_sans_llm_la_ligne_part_a_revoir():
    (changement,) = _secours()
    assert (changement.operation, changement.statut) == (Operation.NON_RECONNUE, Statut.A_REVOIR)
    assert changement.dispositif == "CIR"
    assert vers_lot2.changement_detecte(9, changement) is None  # attend un humain
    # LLM non configuré : même résultat qu'en son absence.
    (sans_fournisseur,) = _secours(ServiceLLM(ClientNonConfigure()))
    assert sans_fournisseur.model_dump(exclude={"cree_le"}) == changement.model_dump(
        exclude={"cree_le"}
    )


def _service(reponse: dict) -> ServiceLLM:
    return ServiceLLM(ClientFactice({"s2_secours": [json.dumps(reponse, ensure_ascii=False)] * 2}))


def test_lecture_llm_verifiee_mot_pour_mot():
    reponse = {
        "modifie": True,
        "operation": "autre",
        "objet": "taux",
        "ancienne_valeur": "30 %",
        "nouvelle_valeur": None,
        "passage": LIGNE[6:],
    }
    (changement,) = _secours(_service(reponse))
    assert changement.methode == Methode.LLM and changement.statut == Statut.A_REVOIR
    assert changement.motifs == [Motif.AUCUNE_FORMULE, Motif.EXTRACTION_LLM]
    assert changement.ancienne_valeur == "30 %"
    assert vers_lot2.changement_detecte(9, changement)["a_revoir"] is True
    assert (
        TEXTE_I_1521[changement.passage.debut : changement.passage.fin] == changement.passage.texte
    )


def test_lecture_llm_inventee_est_ecartee():
    reponse = {
        "modifie": True,
        "operation": "remplacement",
        "ancienne_valeur": "30 %",
        "nouvelle_valeur": "35 %",
        "passage": LIGNE[6:],
    }
    (changement,) = _secours(_service(reponse))
    assert changement.methode == Methode.REGEX  # 35 % n'est pas dans le texte : lecture refusée
    assert changement.nouvelle_valeur is None
