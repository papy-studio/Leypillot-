"""Tables SQLAlchemy, un fichier par lot (chaque lot).

Importer ce paquet enregistre toutes les tables dans ``Base.metadata``.
"""

from leypilot.commun.modeles.collecte import (
    ChangementExtrait,
    Cible,
    Document,
    ExecutionCollecte,
)
from leypilot.commun.modeles.llm import AppelLLM
from leypilot.commun.modeles.mesure import (
    Mesure,
    RattachementAValider,
    ResumeMesure,
    TransitionMesure,
)

__all__ = [
    "AppelLLM",
    "ChangementExtrait",
    "Cible",
    "Document",
    "ExecutionCollecte",
    "Mesure",
    "RattachementAValider",
    "ResumeMesure",
    "TransitionMesure",
]
