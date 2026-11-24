from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from leypilot.commun.config import Reglages
from leypilot.commun.llm import (
    VERSIONS_ACTIVES,
    CacheBase,
    CacheMemoire,
    ClientFactice,
    ClientFournisseur,
    ClientNonConfigure,
    LLMNonConfigure,
    ReponseInvalide,
    ServiceLLM,
    charger_prompt,
    consommation,
    creer_client,
)
from leypilot.commun.llm.service import extraire_json


class Citation(BaseModel):
    citation: str


VALEURS_CITATION: dict[str, object] = {
    "texte": "Le taux de 30 % est remplacé par 20 %.",
    "dispositif": "CII",
    "article_vise": "244 quater B",
    "parametre": "taux",
    "ancienne_valeur": "30 %",
    "nouvelle_valeur": "20 %",
}


@pytest.mark.parametrize("nom", sorted(VERSIONS_ACTIVES))
def test_chaque_prompt_actif_se_charge(nom):
    prompt = charger_prompt(nom)
    assert prompt.systeme and prompt.message
    assert prompt.version == VERSIONS_ACTIVES[nom]


def test_prompt_signale_une_valeur_manquante():
    with pytest.raises(ValueError, match="Valeur manquante"):
        charger_prompt("s3_citation").requete(texte="...")


def test_prompt_inconnu():
    with pytest.raises(ValueError):
        charger_prompt("inexistant")


def test_none_devient_non_precise():
    requete = charger_prompt("s3_citation").requete(**{**VALEURS_CITATION, "ancienne_valeur": None})
    assert "ancienne valeur : non précisé" in requete.message


def test_extraire_json_dans_une_reponse_bavarde():
    assert extraire_json('Voici :\n```json\n{"citation": "x"}\n```') == '{"citation": "x"}'
    with pytest.raises(ReponseInvalide):
        extraire_json("pas de JSON")


def test_le_cache_evite_un_second_appel():
    client = ClientFactice({"s3_citation": ['{"citation": "remplacé par 20 %"}']})
    cache = CacheMemoire()
    service = ServiceLLM(client, cache)

    premier = service.generer("s3_citation", Citation, VALEURS_CITATION)
    second = service.generer("s3_citation", Citation, VALEURS_CITATION)

    assert premier == second == Citation(citation="remplacé par 20 %")
    assert len(client.appels) == 1
    assert len(cache) == 1


def test_forcer_ignore_le_cache():
    client = ClientFactice({"s3_citation": ['{"citation": "a"}', '{"citation": "b"}']})
    service = ServiceLLM(client)
    service.generer("s3_citation", Citation, VALEURS_CITATION)
    assert service.generer("s3_citation", Citation, VALEURS_CITATION, forcer=True).citation == "b"
    assert service.generer("s3_citation", Citation, VALEURS_CITATION).citation == "b"


def test_reponse_invalide_puis_valide():
    client = ClientFactice({"s3_citation": ["je ne sais pas", '{"citation": "ok"}']})
    assert ServiceLLM(client).generer("s3_citation", Citation, VALEURS_CITATION).citation == "ok"


def test_reponses_toujours_invalides():
    client = ClientFactice({"s3_citation": ['{"autre": 1}', '{"autre": 2}']})
    with pytest.raises(ReponseInvalide):
        ServiceLLM(client, tentatives=2).generer("s3_citation", Citation, VALEURS_CITATION)


def test_une_reponse_invalide_n_est_pas_mise_en_cache():
    cache = CacheMemoire()
    client = ClientFactice({"s3_citation": ["???", "???"]})
    with pytest.raises(ReponseInvalide):
        ServiceLLM(client, cache).generer("s3_citation", Citation, VALEURS_CITATION)
    assert len(cache) == 0


def test_client_non_configure_par_defaut():
    client = creer_client(Reglages(llm_fournisseur=""))
    assert isinstance(client, ClientNonConfigure)
    with pytest.raises(LLMNonConfigure):
        ServiceLLM(client).generer("s3_citation", Citation, VALEURS_CITATION)


def test_requete_du_fournisseur_pas_encore_ecrite():
    client = creer_client(Reglages(llm_fournisseur="a-choisir", llm_modele="m", llm_cle_api="k"))
    assert isinstance(client, ClientFournisseur)
    with pytest.raises(LLMNonConfigure, match="pas encore écrite"):
        ServiceLLM(client).generer("s3_citation", Citation, VALEURS_CITATION)


def test_cache_en_base_et_consommation(session):
    debut = datetime(2000, 1, 1, tzinfo=UTC)
    client = ClientFactice({"s3_citation": ['{"citation": "a"}']})
    service = ServiceLLM(client, CacheBase(session))
    service.generer("s3_citation", Citation, VALEURS_CITATION)

    autre_service = ServiceLLM(ClientFactice(), CacheBase(session))
    assert autre_service.generer("s3_citation", Citation, VALEURS_CITATION).citation == "a"

    [ligne] = consommation(session, debut)
    assert ligne.tache == "s3_citation"
    assert ligne.appels == 1
    assert ligne.jetons_entree > 0
