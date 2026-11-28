"""Client du fournisseur : réponses HTTP simulées, aucun appel réseau."""

import json

import httpx
import pytest
from pydantic import BaseModel

from leypilot.commun.llm import (
    ClientFournisseur,
    ErreurLLM,
    LLMNonConfigure,
    RequeteLLM,
    ServiceLLM,
)
from leypilot.commun.llm.client import URL_FOURNISSEURS

REQUETE = RequeteLLM(
    tache="s3_citation", version_prompt="v1", systeme="Consigne", message="Texte", max_jetons=300
)


def reponse_ok(contenu: str, finish_reason: str = "stop") -> dict:
    return {
        "model": "openai/gpt-oss-120b",
        "choices": [
            {"message": {"role": "assistant", "content": contenu}, "finish_reason": finish_reason}
        ],
        "usage": {"prompt_tokens": 90, "completion_tokens": 37},
    }


def client_simule(gestionnaire, modele: str = "openai/gpt-oss-120b") -> ClientFournisseur:
    return ClientFournisseur(
        "groq", modele, "gsk_test", transport=httpx.MockTransport(gestionnaire)
    )


def test_requete_envoyee_au_fournisseur():
    recues: list[httpx.Request] = []

    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        recues.append(requete)
        return httpx.Response(200, json=reponse_ok('{"citation": "a"}'))

    reponse = client_simule(gestionnaire).completer(REQUETE)

    (envoyee,) = recues
    assert str(envoyee.url) == URL_FOURNISSEURS["groq"]
    assert envoyee.headers["Authorization"] == "Bearer gsk_test"
    corps = json.loads(envoyee.content)
    assert corps["model"] == "openai/gpt-oss-120b"
    assert corps["messages"] == [
        {"role": "system", "content": "Consigne"},
        {"role": "user", "content": "Texte"},
    ]
    assert corps["max_tokens"] == 300
    assert corps["temperature"] == 0
    assert corps["reasoning_effort"] == "low"  # gpt-oss raisonne : budget limité
    assert reponse.texte == '{"citation": "a"}'
    assert (reponse.jetons_entree, reponse.jetons_sortie) == (90, 37)


def test_pas_de_reglage_de_raisonnement_pour_les_autres_modeles():
    corps = ClientFournisseur("mistral", "mistral-small-latest", "k").corps(REQUETE)
    assert "reasoning_effort" not in corps


@pytest.mark.parametrize(
    ("statut", "motif"),
    [
        (401, "clé API refusée"),
        (403, "abonnement"),
        (404, "modèle inconnu"),
        (429, "quota"),
        (500, "erreur du fournisseur"),
    ],
)
def test_erreurs_http_traduites(statut, motif):
    def gestionnaire(_: httpx.Request) -> httpx.Response:
        return httpx.Response(statut, json={"error": {"message": "détail du fournisseur"}})

    with pytest.raises(ErreurLLM, match=motif) as erreur:
        client_simule(gestionnaire).completer(REQUETE)
    assert "détail du fournisseur" in str(erreur.value)
    assert "gsk_test" not in str(erreur.value)


def test_reponse_tronquee_refusee():
    # gpt-oss peut épuiser le budget en raisonnant : contenu vide, finish_reason = length.
    def gestionnaire(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=reponse_ok("", finish_reason="length"))

    with pytest.raises(ErreurLLM, match="tronquée"):
        client_simule(gestionnaire).completer(REQUETE)


@pytest.mark.parametrize("corps", [b"pas du json", b'{"choices": []}', b'{"autre": 1}'])
def test_reponse_illisible(corps):
    def gestionnaire(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=corps)

    with pytest.raises(ErreurLLM, match="illisible"):
        client_simule(gestionnaire).completer(REQUETE)


def test_reponse_vide():
    def gestionnaire(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=reponse_ok("   "))

    with pytest.raises(ErreurLLM, match="vide"):
        client_simule(gestionnaire).completer(REQUETE)


@pytest.mark.parametrize("exception", [httpx.ReadTimeout("lent"), httpx.ConnectError("hors ligne")])
def test_panne_reseau_traduite(exception):
    def gestionnaire(requete: httpx.Request) -> httpx.Response:
        raise exception

    with pytest.raises(ErreurLLM):
        client_simule(gestionnaire).completer(REQUETE)


def test_reglages_incomplets():
    with pytest.raises(LLMNonConfigure, match="LLM_CLE_API"):
        ClientFournisseur("groq", "openai/gpt-oss-120b", "").completer(REQUETE)


def test_la_cle_n_apparait_pas_dans_repr():
    assert "gsk_test" not in repr(client_simule(lambda _: httpx.Response(200)))


def test_branche_dans_le_service():
    class Citation(BaseModel):
        citation: str

    def gestionnaire(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=reponse_ok('```json\n{"citation": "20 %"}\n```'))

    resultat = ServiceLLM(client_simule(gestionnaire)).generer(
        "s3_citation",
        Citation,
        {
            "texte": "Le taux de 30 % est remplacé par 20 %.",
            "dispositif": "CII",
            "article_vise": "244 quater B",
            "parametre": "taux",
            "ancienne_valeur": "30 %",
            "nouvelle_valeur": "20 %",
        },
    )
    assert resultat.citation == "20 %"
