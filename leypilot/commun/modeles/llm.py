"""Table de la couche LLM (propriétaire : P2).

``appel_llm`` sert à la fois de cache (une requête identique n'est jamais
payée deux fois) et de journal de consommation (jetons par tâche).
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from leypilot.commun.base import Base, maintenant


class AppelLLM(Base):
    __tablename__ = "appel_llm"

    id: Mapped[int] = mapped_column(primary_key=True)
    cle: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tache: Mapped[str] = mapped_column(String(50), index=True)
    version_prompt: Mapped[str] = mapped_column(String(20))
    modele: Mapped[str] = mapped_column(String(100))
    reponse: Mapped[str] = mapped_column(Text)
    jetons_entree: Mapped[int] = mapped_column(Integer, default=0)
    jetons_sortie: Mapped[int] = mapped_column(Integer, default=0)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=maintenant)
