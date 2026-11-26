import json
from datetime import date

from leypilot.commun.llm import ClientFactice, ClientNonConfigure, ServiceLLM
from leypilot.mesure.contexte import ContexteMemoire, construire_contexte
from leypilot.mesure.dates import DateVigueur
from leypilot.mesure.drapeaux import (
    MOTIF_CITATION,
    MOTIF_DECRET,
    MOTIF_EXTRACTION,
    MOTIF_MONTANT,
    MOTIF_TERMES,
    detecter_doutes,
)
from leypilot.mesure.resume import RedacteurGabarit, ResumeurS3, creer_resumeur
from leypilot.mesure.schemas import Dispositif, NatureDate

DATE_CERTAINE = DateVigueur(date(2026, 1, 1), NatureDate.CERTAINE, "…", "depenses", "regex")
CITATION_LLM = "le taux : « 30 % » est remplacé par le taux : « 20 % »"


def service(*resumes: str, citation: str = CITATION_LLM) -> tuple[ServiceLLM, ClientFactice]:
    client = ClientFactice(
        {
            "s3_citation": [json.dumps({"citation": citation}, ensure_ascii=False)],
            "s3_resume": [json.dumps({"resume": r}, ensure_ascii=False) for r in resumes],
        }
    )
    return ServiceLLM(client), client


# --- Gabarit -------------------------------------------------------------------------


def test_resume_par_gabarit(fabrique):
    produit = ResumeurS3().resumer(fabrique(), DATE_CERTAINE)
    assert produit.texte == (
        "CII : « taux » passe de 30 % à 20 % (article 244 quater B du code général des impôts). "
        "Étape : mesure proposée (amendement ou projet de texte déposé). "
        "Applicable à compter du 1er janvier 2026."
    )
    assert produit.methode == "gabarit"
    assert produit.citation == fabrique().passage_cite
    assert not produit.a_verifier


def test_gabarit_sans_date_et_date_estimee(fabrique):
    gabarit = RedacteurGabarit()
    assert "non précisée" in gabarit.rediger(fabrique(), "", "", None)
    estimee = DateVigueur(
        date(2026, 1, 1), NatureDate.ESTIMEE, None, "droit_commun", "droit_commun"
    )
    assert "estimée au 1er janvier 2026, à confirmer" in gabarit.rediger(
        fabrique(), "", "", estimee
    )


# --- LLM -----------------------------------------------------------------------------


def test_resume_par_llm(fabrique):
    llm, client = service("Le taux du CII baisse de 30 % à 20 % pour les dépenses de 2026.")
    produit = creer_resumeur(llm).resumer(fabrique(), DATE_CERTAINE)
    assert produit.methode == "llm"
    assert produit.texte.startswith("Le taux du CII baisse")
    assert produit.citation == CITATION_LLM
    assert [a.tache for a in client.appels] == ["s3_citation", "s3_resume"]


def test_aucune_donnee_client_dans_les_prompts(fabrique):
    llm, client = service("Résumé.")
    creer_resumeur(llm).resumer(fabrique(), DATE_CERTAINE)
    for appel in client.appels:
        assert "client" not in appel.message.lower()


def test_citation_du_llm_non_verbatim_remplacee_par_celle_de_s2(fabrique):
    llm, _ = service("Résumé.", citation="le taux passe de 30 à 20 %")
    produit = creer_resumeur(llm).resumer(fabrique(), DATE_CERTAINE)
    assert produit.citation == fabrique().passage_cite
    assert not produit.a_verifier


def test_montant_invente_regenere_une_fois(fabrique):
    llm, client = service(
        "Le client type perd 40 000 € par an.",
        "Le taux du CII passe de 30 % à 20 %.",
    )
    produit = creer_resumeur(llm).resumer(fabrique(), DATE_CERTAINE)
    assert produit.methode == "llm"
    assert "€" not in produit.texte
    assert [a.tache for a in client.appels] == ["s3_citation", "s3_resume", "s3_resume"]


def test_montant_invente_deux_fois_donne_le_gabarit(fabrique):
    llm, _ = service("Perte de 40 000 €.", "Toujours 40 000 € de perte.")
    produit = creer_resumeur(llm).resumer(fabrique(), DATE_CERTAINE)
    assert produit.methode == "gabarit"
    assert "€" not in produit.texte
    assert MOTIF_MONTANT not in produit.motifs


def test_montant_de_la_citation_autorise(fabrique):
    texte = "Le plafond de dépenses est porté de 400 000 € à 500 000 €."
    changement = fabrique(
        parametre="plafond",
        ancienne_valeur="400 000 €",
        nouvelle_valeur="500 000 €",
        texte_source=texte,
        passage_cite=texte,
    )
    llm, _ = service("Le plafond du CII passe de 400 000 € à 500 000 €.", citation=texte)
    produit = creer_resumeur(llm).resumer(changement)
    assert produit.methode == "llm"
    assert "500 000 €" in produit.texte


def test_sans_llm_le_gabarit_n_est_pas_en_attente(fabrique):
    produit = creer_resumeur().resumer(fabrique(), DATE_CERTAINE)
    assert (produit.methode, produit.en_attente) == ("gabarit", False)


def test_llm_non_configure_donne_un_resume_provisoire_en_attente(fabrique):
    produit = creer_resumeur(ServiceLLM(ClientNonConfigure())).resumer(fabrique(), DATE_CERTAINE)
    assert produit.methode == "gabarit"
    assert produit.texte.startswith("CII :")
    assert produit.en_attente


def test_reponse_illisible_apres_les_tentatives_donne_un_resume_en_attente(fabrique):
    client = ClientFactice({"s3_citation": ["???", "???"]})
    produit = creer_resumeur(ServiceLLM(client, tentatives=2)).resumer(fabrique())
    assert len(client.appels) == 2  # une nouvelle tentative, puis abandon
    assert (produit.methode, produit.en_attente) == ("gabarit", True)


# --- Drapeau « à vérifier » ------------------------------------------------------


def test_drapeau_decret_a_paraitre(fabrique):
    changement = fabrique(
        texte_source=fabrique().texte_source + " Les modalités sont fixées par décret."
    )
    assert MOTIF_DECRET in detecter_doutes(changement)


def test_drapeau_extraction_a_revoir(fabrique):
    assert detecter_doutes(fabrique(a_revoir=True)) == [MOTIF_EXTRACTION]


def test_drapeau_termes_non_definis(fabrique):
    passage = "les dépenses de « prototypes de nouveaux produits » sont éligibles"
    changement = fabrique(passage_cite=passage, texte_source=f"Désormais, {passage}.")
    [motif] = detecter_doutes(changement)
    assert motif.startswith(MOTIF_TERMES)
    assert detecter_doutes(changement, frozenset({"prototypes de nouveaux produits"})) == []

    definie = fabrique(
        passage_cite=passage,
        texte_source=f"Désormais, {passage}. On entend par « prototypes de nouveaux produits » ...",
    )
    assert detecter_doutes(definie) == []


def test_aucun_drapeau_sur_un_texte_clair(fabrique):
    assert detecter_doutes(fabrique()) == []


def test_drapeau_citation_introuvable(fabrique):
    changement = fabrique(passage_cite="passage qui n'existe pas dans le texte source")
    produit = ResumeurS3().resumer(changement)
    assert MOTIF_CITATION in produit.motifs
    assert produit.a_verifier


# --- Contexte ------------------------------------------------------------------------


def test_contexte_retrouve_par_identifiant(fabrique):
    source = ContexteMemoire(
        articles={"CGI art. 244 quater B": "Texte de l'article 244 quater B en vigueur."},
        doctrine={Dispositif.CII: "BOI-BIC-RICI-10-10 : doctrine du CII."},
    )
    contexte = construire_contexte(source, fabrique())
    assert "Texte de l'article 244 quater B" in contexte
    assert "doctrine du CII" in contexte
    assert construire_contexte(ContexteMemoire(), fabrique()) == "Aucun contexte disponible."
