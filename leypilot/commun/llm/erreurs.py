"""Erreurs de la couche LLM.

Tous les appelants rattrapent ``ErreurLLM`` : une panne du LLM ne doit jamais
bloquer la chaîne, elle fait basculer sur le traitement sans LLM (gabarit).
"""


class ErreurLLM(Exception):
    """Erreur générique de la couche LLM."""


class LLMNonConfigure(ErreurLLM):
    """Aucun fournisseur n'est configuré, ou sa requête n'est pas encore écrite."""


class ReponseInvalide(ErreurLLM):
    """La réponse du LLM ne respecte pas le format attendu."""
