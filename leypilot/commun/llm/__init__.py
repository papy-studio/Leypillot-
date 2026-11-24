"""Couche LLM partagée (P2).

Interface unique pour tous les lots : prompts versionnés, cache, validation
JSON par Pydantic et filtre anti-montant. Le fournisseur n'est pas encore
choisi : sans configuration, ``creer_client`` renvoie un client qui lève
``LLMNonConfigure`` et chaque lot bascule sur son traitement sans LLM.
"""

from leypilot.commun.llm.anti_montant import (
    chiffres_en_dur,
    contient_montant,
    extraire_montants,
    montants_non_justifies,
)
from leypilot.commun.llm.cache import CacheBase, CacheMemoire, consommation, empreinte_requete
from leypilot.commun.llm.client import (
    ClientFactice,
    ClientFournisseur,
    ClientLLM,
    ClientNonConfigure,
    ReponseLLM,
    RequeteLLM,
    creer_client,
)
from leypilot.commun.llm.erreurs import ErreurLLM, LLMNonConfigure, ReponseInvalide
from leypilot.commun.llm.prompts import VERSIONS_ACTIVES, charger_prompt
from leypilot.commun.llm.service import ServiceLLM

__all__ = [
    "VERSIONS_ACTIVES",
    "CacheBase",
    "CacheMemoire",
    "ClientFactice",
    "ClientFournisseur",
    "ClientLLM",
    "ClientNonConfigure",
    "ErreurLLM",
    "LLMNonConfigure",
    "ReponseInvalide",
    "ReponseLLM",
    "RequeteLLM",
    "ServiceLLM",
    "charger_prompt",
    "chiffres_en_dur",
    "consommation",
    "contient_montant",
    "creer_client",
    "empreinte_requete",
    "extraire_montants",
    "montants_non_justifies",
]
