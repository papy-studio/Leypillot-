"""Client de l'API Légifrance via PISTE (OAuth2 « client credentials »).

Rôle dans le MVP : vérifier ponctuellement un article (état, version en vigueur) et
servir de recours si les fichiers de la DILA manquent. La source principale du JO et
des codes reste l'open data de la DILA (voir docs/adr/0001-dila-source-principale.md).

- jeton : https://oauth.piste.gouv.fr/api/oauth/token, valable 3 600 s ;
- quota par défaut : 20 requêtes par seconde, HTTP 429 au-delà : pause entre requêtes ;
- identifiant et secret dans le ``.env`` (PISTE_CLIENT_ID, PISTE_CLIENT_SECRET).

Test de l'accès, sans afficher le secret : ``python -m leypilot.collecte piste``.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from leypilot.collecte.config import ReglagesCollecte
from leypilot.collecte.sources.base import AGENT

URL_JETON = "https://oauth.piste.gouv.fr/api/oauth/token"
URL_API = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
ARTICLE_TEST = "LEGIARTI000046869153"  # article réel du CGI, vu dans les fichiers LEGI
PAUSE_SECONDES = 0.1  # 10 requêtes par seconde au plus, sous le quota de 20
MARGE_JETON = 60  # le jeton est renouvelé une minute avant son expiration


class ErreurPiste(RuntimeError):
    pass


CONSEILS = {
    401: "jeton refusé : l'API Légifrance est-elle ajoutée à l'application PISTE ?",
    403: "accès refusé : conditions d'utilisation de l'API acceptées en production ?",
    404: "adresse inconnue : vérifier le chemin dans la documentation de PISTE",
    429: "quota dépassé : réessayer dans une minute",
}


class ClientPiste:
    def __init__(self, reglages: ReglagesCollecte, client: httpx.Client | None = None) -> None:
        if not reglages.piste_client_id or not reglages.piste_client_secret.get_secret_value():
            raise ErreurPiste("PISTE_CLIENT_ID ou PISTE_CLIENT_SECRET absent du .env")
        self._reglages = reglages
        self._http = client or httpx.Client(headers={"User-Agent": AGENT}, timeout=30)
        self._jeton: str | None = None
        self._expire_a = 0.0
        self._dernier_appel = 0.0
        self.duree_jeton: int | None = None

    def _jeton_valide(self) -> str:
        if self._jeton and time.monotonic() < self._expire_a - MARGE_JETON:
            return self._jeton
        reponse = self._http.post(
            URL_JETON,
            data={
                "grant_type": "client_credentials",
                "client_id": self._reglages.piste_client_id,
                "client_secret": self._reglages.piste_client_secret.get_secret_value(),
                "scope": "openid",
            },
        )
        if reponse.status_code != 200:
            # Le corps de la réponse peut citer l'identifiant : on ne l'affiche pas.
            raise ErreurPiste(f"jeton refusé : HTTP {reponse.status_code}")
        corps = reponse.json()
        if "access_token" not in corps:
            raise ErreurPiste("réponse sans jeton")
        self._jeton = str(corps["access_token"])
        self.duree_jeton = int(corps.get("expires_in", 3600))
        self._expire_a = time.monotonic() + self.duree_jeton
        return self._jeton

    def appeler(self, chemin: str, corps: dict[str, Any]) -> dict[str, Any]:
        attente = PAUSE_SECONDES - (time.monotonic() - self._dernier_appel)
        if attente > 0:
            time.sleep(attente)
        reponse = self._http.post(
            f"{URL_API}{chemin}",
            json=corps,
            headers={
                "Authorization": f"Bearer {self._jeton_valide()}",
                "Accept": "application/json",
            },
        )
        self._dernier_appel = time.monotonic()
        if reponse.status_code != 200:
            conseil = CONSEILS.get(reponse.status_code, "voir la documentation de PISTE")
            raise ErreurPiste(f"{chemin} : HTTP {reponse.status_code}, {conseil}")
        return reponse.json()

    def article(self, identifiant: str) -> dict[str, Any]:
        """Article LEGI (texte, état, dates de vigueur) : ``consult/getArticle``."""
        return self.appeler("/consult/getArticle", {"id": identifiant}).get("article") or {}

    def fermer(self) -> None:
        self._http.close()


def tester_acces(reglages: ReglagesCollecte) -> str:
    """Obtient un jeton puis lit un article. Renvoie un compte rendu sans aucun secret."""
    client = ClientPiste(reglages)
    try:
        debut = time.monotonic()
        article = client.article(ARTICLE_TEST)
        duree = time.monotonic() - debut
    finally:
        client.fermer()
    return (
        f"Jeton obtenu (valable {client.duree_jeton} s). "
        f"Article {article.get('num', '?')} lu en {duree:.1f} s, état {article.get('etat', '?')}."
    )
