"""Contrat d'interface du lot 3 (P3), lu par P4 et P5.

Brouillon à faire relire par P4 et P5 avant de le figer.
Les montants sont des Decimal (en euros, arrondis au centime).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class EtapeTrace(BaseModel):
    """Une ligne de la trace de calcul affichée au consultant."""

    libelle: str  # "Assiette retenue"
    valeur: Decimal  # 400000
    source: str  # lien Légifrance, ou "profil client" pour une donnée du client


class MesureChiffrable(BaseModel):
    """Ce que le moteur lit d'une mesure. P2 fournit ce format avec vers_mesure_chiffrable()."""

    mesure_id: int
    dispositif: str  # "CII"
    parametre: str  # une clé du YAML : "taux", "plafond_depenses"...
    ancienne_valeur: Decimal  # 0.30
    nouvelle_valeur: Decimal  # 0.20
    date_effet: date  # 2026-01-01
    date_certaine: bool = True  # False si P2 a estimé la date
    citation: str  # passage du texte officiel


class ResultatSimulation(BaseModel):
    """Ce que le moteur renvoie pour un client et une mesure.

    ecart = aide_loi_actuelle - aide_reforme : positif quand le client perd de l'aide.
    """

    client_id: int
    mesure_id: int
    dispositif: str
    aide_loi_actuelle: Decimal | None
    aide_reforme: Decimal | None
    ecart: Decimal | None
    statut: str  # "ok" | "en_attente" | "impossible"
    motif: str | None = None  # pourquoi "en_attente" ou "impossible"
    provisoire: bool = False  # True si la date d'effet est estimée
    champs_manquants: list[str] = []
    trace_loi_actuelle: list[EtapeTrace] = []
    trace_reforme: list[EtapeTrace] = []
    empreinte: str
