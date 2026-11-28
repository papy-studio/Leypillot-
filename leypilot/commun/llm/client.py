"""Clients LLM : l'interface commune et ses implémentations.

- ``ClientFournisseur`` appelle le fournisseur réglé dans le .env (Groq pour le
  prototype). Il parle le format « chat completions » d'OpenAI, que Groq,
  Mistral et Vercel AI Gateway acceptent : changer de fournisseur revient à
  changer ``LLM_FOURNISSEUR``, ``LLM_MODELE`` et ``LLM_CLE_API`` ;
- ``ClientNonConfigure`` est utilisé quand aucun fournisseur n'est réglé ;
  le lot 2 bascule alors sur ses gabarits ;
- ``ClientFactice`` sert aux tests et aux autres lots, sans clé API.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from leypilot.commun.config import Reglages
from leypilot.commun.llm.erreurs import ErreurLLM, LLMNonConfigure

# Adresse de l'API « chat completions » de chaque fournisseur accepté.
URL_FOURNISSEURS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
    "vercel": "https://ai-gateway.vercel.sh/v1/chat/completions",
}

# Modèles qui raisonnent avant de répondre (gpt-oss) : le raisonnement consomme le
# budget de jetons. On le limite, sinon la réponse peut revenir vide.
_MODELES_RAISONNEMENT = ("gpt-oss",)

_MESSAGES_HTTP = {
    401: "clé API refusée",
    403: "accès refusé (abonnement ou moyen de paiement manquant ?)",
    404: "modèle inconnu ou non disponible pour cette clé",
    429: "quota dépassé, réessayer plus tard",
}


@dataclass(frozen=True)
class RequeteLLM:
    """Ce qui est envoyé au modèle. Ne contient jamais de donnée client."""

    tache: str
    version_prompt: str
    systeme: str
    message: str
    max_jetons: int = 1024


@dataclass(frozen=True)
class ReponseLLM:
    texte: str
    modele: str
    jetons_entree: int = 0
    jetons_sortie: int = 0


class ClientLLM(Protocol):
    def completer(self, requete: RequeteLLM) -> ReponseLLM: ...


class ClientNonConfigure:
    """Client utilisé tant qu'aucun fournisseur n'est configuré."""

    def completer(self, requete: RequeteLLM) -> ReponseLLM:
        raise LLMNonConfigure("Aucun fournisseur LLM configuré (LLM_FOURNISSEUR est vide).")


class ClientFournisseur:
    """Client du fournisseur réglé dans le .env (format « chat completions »).

    Toute erreur (réseau, délai, clé, quota, réponse vide ou tronquée) devient une
    ``ErreurLLM`` : l'appelant bascule alors sur son traitement sans LLM.
    """

    def __init__(
        self,
        fournisseur: str,
        modele: str,
        cle_api: str,
        delai_secondes: float = 60.0,
        transport: httpx.BaseTransport | None = None,  # pour les tests
    ):
        self.fournisseur = fournisseur.strip().lower()
        self.modele = modele
        self.cle_api = cle_api
        self.delai_secondes = delai_secondes
        self.transport = transport

    def __repr__(self) -> str:  # n'affiche jamais la clé
        return f"ClientFournisseur({self.fournisseur!r}, {self.modele!r})"

    def corps(self, requete: RequeteLLM) -> dict[str, Any]:
        corps: dict[str, Any] = {
            "model": self.modele,
            "messages": [
                {"role": "system", "content": requete.systeme},
                {"role": "user", "content": requete.message},
            ],
            "max_tokens": requete.max_jetons,
            "temperature": 0,  # même texte, même réponse : résultats reproductibles
        }
        if any(nom in self.modele for nom in _MODELES_RAISONNEMENT):
            corps["reasoning_effort"] = "low"
        return corps

    def completer(self, requete: RequeteLLM) -> ReponseLLM:
        url = URL_FOURNISSEURS.get(self.fournisseur)
        if url is None:
            connus = ", ".join(sorted(URL_FOURNISSEURS))
            raise LLMNonConfigure(
                f"Fournisseur LLM inconnu : {self.fournisseur!r} (acceptés : {connus})."
            )
        if not self.modele or not self.cle_api:
            raise LLMNonConfigure("LLM_MODELE ou LLM_CLE_API manquant dans le .env.")

        try:
            with httpx.Client(timeout=self.delai_secondes, transport=self.transport) as http:
                reponse = http.post(
                    url,
                    json=self.corps(requete),
                    headers={"Authorization": f"Bearer {self.cle_api}"},
                )
        except httpx.TimeoutException as erreur:
            raise ErreurLLM(
                f"{self.fournisseur} : pas de réponse en {self.delai_secondes:g} s."
            ) from erreur
        except httpx.HTTPError as erreur:
            raise ErreurLLM(f"{self.fournisseur} : erreur réseau ({erreur}).") from erreur

        if reponse.status_code != 200:
            raise ErreurLLM(self._message_erreur(reponse))
        return self._lire(reponse)

    def _message_erreur(self, reponse: httpx.Response) -> str:
        code = reponse.status_code
        motif = _MESSAGES_HTTP.get(code, "erreur du fournisseur")
        try:
            detail = reponse.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        return f"{self.fournisseur} : HTTP {code}, {motif}" + (f" ({detail})" if detail else "")

    def _lire(self, reponse: httpx.Response) -> ReponseLLM:
        try:
            donnees = reponse.json()
            choix = donnees["choices"][0]
            texte = choix["message"].get("content") or ""
            usage = donnees.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as erreur:
            raise ErreurLLM(f"{self.fournisseur} : réponse illisible.") from erreur

        if choix.get("finish_reason") == "length":
            raise ErreurLLM(f"{self.fournisseur} : réponse tronquée (budget de jetons atteint).")
        if not texte.strip():
            raise ErreurLLM(f"{self.fournisseur} : réponse vide.")
        return ReponseLLM(
            texte=texte,
            modele=donnees.get("model", self.modele),
            jetons_entree=int(usage.get("prompt_tokens", 0)),
            jetons_sortie=int(usage.get("completion_tokens", 0)),
        )


@dataclass
class ClientFactice:
    """Client de test : renvoie, pour chaque tâche, les réponses préparées dans l'ordre."""

    reponses: dict[str, list[str]] = field(default_factory=dict)
    modele: str = "factice"
    appels: list[RequeteLLM] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._files = {tache: deque(textes) for tache, textes in self.reponses.items()}

    def ajouter(self, tache: str, *textes: str) -> None:
        self._files.setdefault(tache, deque()).extend(textes)

    def completer(self, requete: RequeteLLM) -> ReponseLLM:
        self.appels.append(requete)
        file = self._files.get(requete.tache)
        if not file:
            raise ErreurLLM(f"Pas de réponse préparée pour la tâche {requete.tache!r}.")
        texte = file.popleft()
        return ReponseLLM(
            texte=texte,
            modele=self.modele,
            jetons_entree=len(requete.systeme + requete.message) // 4,
            jetons_sortie=len(texte) // 4,
        )


def creer_client(reglages: Reglages | None = None) -> ClientLLM:
    """Client correspondant à la configuration (.env)."""
    if reglages is None:
        from leypilot.commun.config import reglages as reglages_par_defaut

        reglages = reglages_par_defaut
    if not reglages.llm_fournisseur:
        return ClientNonConfigure()
    return ClientFournisseur(reglages.llm_fournisseur, reglages.llm_modele, reglages.llm_cle_api)
