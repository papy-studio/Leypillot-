"""Service LLM partagé : prompt versionné → cache → client → JSON validé par Pydantic.

C'est le point d'entrée des autres lots (S2 secours, M3, G4) :

    service = ServiceLLM(creer_client(), CacheBase(session))
    resultat = service.generer("s3_citation", MonSchema, {"texte": ..., ...})
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from leypilot.commun.llm.cache import CacheLLM, CacheMemoire, empreinte_requete
from leypilot.commun.llm.client import ClientLLM
from leypilot.commun.llm.erreurs import ReponseInvalide
from leypilot.commun.llm.prompts import charger_prompt

journal = logging.getLogger(__name__)

_BLOC_JSON = re.compile(r"\{.*\}", re.DOTALL)


def extraire_json(texte: str) -> str:
    """Isole l'objet JSON d'une réponse, même entourée de texte ou de balises ```json."""
    trouve = _BLOC_JSON.search(texte)
    if trouve is None:
        raise ReponseInvalide("Aucun objet JSON dans la réponse du LLM.")
    return trouve.group(0)


def valider[T: BaseModel](texte: str, schema: type[T]) -> T:
    try:
        return schema.model_validate_json(extraire_json(texte))
    except ValidationError as erreur:
        raise ReponseInvalide(f"Réponse hors format {schema.__name__} : {erreur}") from erreur


class ServiceLLM:
    def __init__(self, client: ClientLLM, cache: CacheLLM | None = None, tentatives: int = 2):
        if tentatives < 1:
            raise ValueError("Il faut au moins une tentative.")
        self.client = client
        self.cache = cache if cache is not None else CacheMemoire()
        self.tentatives = tentatives

    def generer[T: BaseModel](
        self,
        nom_prompt: str,
        schema: type[T],
        valeurs: Mapping[str, object],
        *,
        version: str | None = None,
        forcer: bool = False,
    ) -> T:
        """Réponse validée par ``schema``.

        ``valeurs`` remplit les variables ``$nom`` du prompt.
        ``forcer=True`` ignore le cache (régénération) et remplace l'entrée.
        Lève ``ErreurLLM`` (client) ou ``ReponseInvalide`` (format) en cas d'échec.
        """
        requete = charger_prompt(nom_prompt, version).requete(**valeurs)
        cle = empreinte_requete(requete)

        if not forcer and (en_cache := self.cache.lire(cle)) is not None:
            try:
                return valider(en_cache.texte, schema)
            except ReponseInvalide:
                journal.warning("Entrée de cache illisible pour %s, nouvel appel.", nom_prompt)

        derniere_erreur: ReponseInvalide | None = None
        for tentative in range(1, self.tentatives + 1):
            reponse = self.client.completer(requete)
            try:
                resultat = valider(reponse.texte, schema)
            except ReponseInvalide as erreur:
                journal.warning("Réponse invalide (%s, tentative %d).", nom_prompt, tentative)
                derniere_erreur = erreur
                continue
            self.cache.ecrire(cle, requete, reponse)
            return resultat
        raise ReponseInvalide(
            f"{nom_prompt} : aucune réponse valide après {self.tentatives} tentatives."
        ) from derniere_erreur
