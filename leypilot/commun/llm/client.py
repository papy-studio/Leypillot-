"""Clients LLM : l'interface commune et ses implémentations.

Le fournisseur (Claude, Mistral…) n'est pas encore choisi. ``ClientFournisseur``
contient la requête à écrire. En attendant :

- ``ClientNonConfigure`` est utilisé quand aucun fournisseur n'est réglé ;
  le lot 2 bascule alors sur ses gabarits ;
- ``ClientFactice`` sert aux tests et aux autres lots, sans clé API.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from leypilot.commun.config import Reglages
from leypilot.commun.llm.erreurs import ErreurLLM, LLMNonConfigure


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
    """Client du fournisseur retenu par l'équipe.

    La requête n'est pas écrite : le choix du fournisseur est en attente.
    Tant qu'elle ne l'est pas, ``completer`` lève ``LLMNonConfigure`` et la
    chaîne continue sans LLM.
    """

    def __init__(self, fournisseur: str, modele: str, cle_api: str, delai_secondes: float = 60.0):
        self.fournisseur = fournisseur
        self.modele = modele
        self.cle_api = cle_api
        self.delai_secondes = delai_secondes

    def completer(self, requete: RequeteLLM) -> ReponseLLM:
        # À ÉCRIRE quand l'équipe aura choisi le fournisseur :
        #   1. envoyer requete.systeme (consigne) et requete.message au modèle self.modele,
        #      avec self.cle_api et un délai maximal de self.delai_secondes ;
        #   2. limiter la réponse à requete.max_jetons ;
        #   3. renvoyer ReponseLLM(texte, modele, jetons_entree, jetons_sortie) ;
        #   4. traduire toute erreur du fournisseur (réseau, quota, refus) en ErreurLLM.
        raise LLMNonConfigure(
            f"Requête au fournisseur {self.fournisseur!r} pas encore écrite "
            "(voir leypilot/commun/llm/client.py)."
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
