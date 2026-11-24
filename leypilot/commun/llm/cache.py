"""Cache des réponses du LLM.

La clé est l'empreinte SHA-256 de la requête complète : tâche, version du
prompt, consigne et message (qui contient le texte). Changer de version de
prompt invalide donc naturellement le cache.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from leypilot.commun.llm.client import ReponseLLM, RequeteLLM
from leypilot.commun.modeles.llm import AppelLLM


def empreinte_requete(requete: RequeteLLM) -> str:
    contenu = json.dumps(
        [requete.tache, requete.version_prompt, requete.systeme, requete.message],
        ensure_ascii=False,
    )
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


class CacheLLM(Protocol):
    def lire(self, cle: str) -> ReponseLLM | None: ...

    def ecrire(self, cle: str, requete: RequeteLLM, reponse: ReponseLLM) -> None: ...


class CacheMemoire:
    def __init__(self) -> None:
        self._entrees: dict[str, ReponseLLM] = {}

    def __len__(self) -> int:
        return len(self._entrees)

    def lire(self, cle: str) -> ReponseLLM | None:
        return self._entrees.get(cle)

    def ecrire(self, cle: str, requete: RequeteLLM, reponse: ReponseLLM) -> None:
        self._entrees[cle] = reponse


class CacheBase:
    """Cache persistant dans la table ``appel_llm``."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def lire(self, cle: str) -> ReponseLLM | None:
        appel = self.session.scalar(select(AppelLLM).where(AppelLLM.cle == cle))
        if appel is None:
            return None
        return ReponseLLM(appel.reponse, appel.modele, appel.jetons_entree, appel.jetons_sortie)

    def ecrire(self, cle: str, requete: RequeteLLM, reponse: ReponseLLM) -> None:
        appel = self.session.scalar(select(AppelLLM).where(AppelLLM.cle == cle))
        if appel is None:
            appel = AppelLLM(cle=cle)
            self.session.add(appel)
        appel.tache = requete.tache
        appel.version_prompt = requete.version_prompt
        appel.modele = reponse.modele
        appel.reponse = reponse.texte
        appel.jetons_entree = reponse.jetons_entree
        appel.jetons_sortie = reponse.jetons_sortie
        self.session.flush()


@dataclass(frozen=True)
class Consommation:
    tache: str
    appels: int
    jetons_entree: int
    jetons_sortie: int


def consommation(session: Session, depuis: datetime) -> list[Consommation]:
    """Jetons consommés par tâche depuis une date, pour suivre le budget mensuel."""
    lignes = session.execute(
        select(
            AppelLLM.tache,
            func.count(AppelLLM.id),
            func.coalesce(func.sum(AppelLLM.jetons_entree), 0),
            func.coalesce(func.sum(AppelLLM.jetons_sortie), 0),
        )
        .where(AppelLLM.cree_le >= depuis)
        .group_by(AppelLLM.tache)
        .order_by(AppelLLM.tache)
    )
    return [Consommation(t, int(n), int(e), int(s)) for t, n, e, s in lignes]
