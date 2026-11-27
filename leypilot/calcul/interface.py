"""Contrat d'interface du lot 3 (P3), lu par P4 et P5.

Brouillon à faire relire par P4 et P5 avant de le figer.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class EtapeTrace(BaseModel):
    """Une ligne de la trace de calcul affichée au consultant."""

    libelle: str  # "Assiette retenue"
    valeur: float  # 400000
    source: str  # lien Légifrance


class MesureChiffrable(BaseModel):
    """Ce que le moteur lit d'une mesure de P2 (format à valider avec P2)."""

    mesure_id: int
    dispositif: str  # "CII"
    parametre: str  # nom du paramètre dans le YAML, par exemple "taux"
    ancienne_valeur: float  # 0.30
    nouvelle_valeur: float  # 0.20
    date_effet: date  # 2026-01-01
    citation: str  # passage du texte officiel


class ResultatSimulation(BaseModel):
    """Ce que le moteur renvoie pour un client et une mesure."""

    client_id: int
    mesure_id: int
    dispositif: str
    aide_loi_actuelle: float | None
    aide_reforme: float | None
    ecart: float | None
    statut: str  # "ok" | "en_attente" | "impossible"
    champs_manquants: list[str] = []
    trace: list[EtapeTrace] = []
    empreinte: str