"""Fil rouge client B, lot 1 puis lot 2 : de l'amendement au JO, sur les vrais textes.

La baisse du taux du CII de 30 % à 20 % vient de l'amendement AN I-2211 au projet de loi
de finances pour 2025 (guillemet fermant manquant dans l'original), devenu l'article 56
de la loi n° 2025-127 du 14 février 2025 (JO du 15 février 2025).

Les textes sont réels (``donnees_exemple/lot1_corpus``) ; les identifiants techniques et
la date de dépôt de l'amendement sont des valeurs de test.
"""

from datetime import date
from pathlib import Path

from leypilot.collecte import depot, vers_lot2
from leypilot.collecte.completude import Rapport
from leypilot.collecte.sources.base import Collecte, DocumentBrut, Source, TypeTexte
from leypilot.collecte.textes import normaliser
from leypilot.commun.modeles.collecte import ChangementExtrait, Document
from leypilot.commun.modeles.mesure import Mesure
from leypilot.mesure.schemas import Changement, StatutMesure
from leypilot.mesure.suivi import SuiviMesures

CORPUS = Path(__file__).parents[2] / "donnees_exemple" / "lot1_corpus"
LF2025 = (CORPUS / "lf2025.txt").read_text(encoding="utf-8")
ARTICLE_56 = LF2025[LF2025.index("Article 56") : LF2025.index("Article 57")]
S = StatutMesure


def _document(source, identifiant, type_texte, jour, texte, **champs) -> DocumentBrut:
    return DocumentBrut(
        source=source,
        identifiant=identifiant,
        nature=type_texte.value.upper(),
        type_texte=type_texte,
        titre=None,
        date_document=jour,
        url_officielle="https://www.legifrance.gouv.fr/",
        texte=normaliser(texte),
        **champs,
    )


ETAPES = [
    _document(
        Source.AN,
        "AMANR5L17PO59048B0324P0D1N002211",
        TypeTexte.AMENDEMENT,
        date(2024, 10, 17),
        (CORPUS / "an_I-2211.txt").read_text(encoding="utf-8"),
        numero_amendement="I-2211",
    ),
    # Adoption définitive le 6 février 2025 (texte considéré comme adopté, 49.3).
    _document(Source.AN, "TA-PLF2025", TypeTexte.TEXTE_ADOPTE, date(2025, 2, 6), ARTICLE_56),
    _document(
        Source.JORF,
        "JORFTEXT-LF2025",
        TypeTexte.LOI,
        date(2025, 2, 15),
        ARTICLE_56,
        nor="ECOX0000000L",
    ),
]


def _vers_lot2(session, resultat) -> list[Changement]:
    """Changements du lot 1 qui portent sur le taux du CII, au format du lot 2."""
    sortie = []
    for changement_id in resultat.changements:
        ligne = session.get(ChangementExtrait, changement_id)
        document = session.get(Document, ligne.document_id)
        assemble = vers_lot2.assembler_pour_lot2(
            document.id, depot._brut(document), ligne.id, depot._schema(ligne)
        )
        if assemble and assemble["ancienne_valeur"] == "30 %":
            sortie.append(Changement.model_validate(assemble))
    return sortie


def test_fil_rouge_client_b_du_lot_1_au_lot_2(session):
    suivi = SuiviMesures(session)
    mesure_id = None
    for etape in ETAPES:
        collecte = Collecte(etape.source, "fil rouge", [etape], Rapport(1, 1), 1)
        resultat = depot.enregistrer_collecte(session, collecte)
        (changement,) = _vers_lot2(session, resultat)

        # Lot 1 : le changement attendu, prouvé mot pour mot.
        assert (changement.dispositif, changement.parametre) == ("CII", "taux")
        assert (changement.ancienne_valeur, changement.nouvelle_valeur) == ("30 %", "20 %")
        assert changement.article_vise == "article 244 quater B du code général des impôts"
        assert changement.passage_cite in changement.texte_source

        # Lot 2 : une seule mesure suit les trois étapes.
        traite = suivi.traiter(changement)
        mesure_id = mesure_id or traite.mesure_id
        assert traite.mesure_id == mesure_id

    mesure = session.get(Mesure, mesure_id)
    assert session.query(Mesure).count() == 1
    assert [t.vers_statut for t in mesure.transitions] == [S.PROPOSEE, S.VOTEE, S.PUBLIEE]
    assert mesure.numeros_amendement == ["I-2211"]
    assert mesure.nor == "ECOX0000000L"
    # La clause d'application recopiée par le lot 1 donne la date au lot 2.
    assert mesure.date_entree_vigueur == date(2025, 1, 1)
