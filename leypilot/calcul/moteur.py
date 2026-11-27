"""Moteur de calcul déterministe du lot 3 (P3). Le LLM n'intervient jamais ici."""

from __future__ import annotations

import hashlib
import json
from datetime import date

from leypilot.calcul.interface import EtapeTrace, MesureChiffrable, ResultatSimulation
from leypilot.calcul.parametres import charger, valeur_a_date

VERSION_MOTEUR = "0.1.0"
CHAMPS_OBLIGATOIRES_CII = ["depenses_innovation"]


def calculer_cii(depenses: float, taux: float, plafond: float, source: str):
    """CII = min(dépenses, plafond) x taux. Renvoie le montant et la trace."""
    assiette = min(depenses, plafond)
    montant = round(assiette * taux, 2)
    trace = [
        EtapeTrace(libelle="Dépenses d'innovation déclarées", valeur=depenses, source=source),
        EtapeTrace(libelle="Plafond des dépenses", valeur=plafond, source=source),
        EtapeTrace(libelle="Assiette retenue", valeur=assiette, source=source),
        EtapeTrace(libelle="Taux appliqué", valeur=taux, source=source),
        EtapeTrace(libelle="Crédit d'impôt innovation", valeur=montant, source=source),
    ]
    return montant, trace


def empreinte(entrees: dict, mesure: MesureChiffrable, exercice: int) -> str:
    """Même entrées + même mesure + même version du moteur = même empreinte."""
    contenu = json.dumps(
        [entrees, mesure.model_dump(mode="json"), exercice, VERSION_MOTEUR],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


def simuler_mesure(
    client_id: int, entrees: dict, mesure: MesureChiffrable, exercice: int
) -> ResultatSimulation:
    """Compare « loi actuelle » et « réforme » pour un client, sur un exercice."""
    signature = empreinte(entrees, mesure, exercice)
    manquants = [champ for champ in CHAMPS_OBLIGATOIRES_CII if entrees.get(champ) is None]
    if manquants:
        return ResultatSimulation(
            client_id=client_id,
            mesure_id=mesure.mesure_id,
            dispositif=mesure.dispositif,
            aide_loi_actuelle=None,
            aide_reforme=None,
            ecart=None,
            statut="impossible",
            champs_manquants=manquants,
            empreinte=signature,
        )

    parametres = charger(mesure.dispositif)
    jour = date(exercice, 12, 31)
    plafond = valeur_a_date(parametres["plafond_depenses"], jour)
    taux_actuel = valeur_a_date(parametres["taux"], jour)
    source = parametres["taux"]["reference"]

    # La réforme : le paramètre visé par la mesure change à sa date d'effet.
    taux_reforme = mesure.nouvelle_valeur if jour >= mesure.date_effet else taux_actuel

    depenses = entrees["depenses_innovation"]
    aide_actuelle, _ = calculer_cii(depenses, taux_actuel, plafond, source)
    aide_reforme, trace = calculer_cii(depenses, taux_reforme, plafond, source)
    ecart = round(aide_actuelle - aide_reforme, 2)
    trace.append(EtapeTrace(libelle="Écart avec la loi actuelle", valeur=ecart, source=source))

    return ResultatSimulation(
        client_id=client_id,
        mesure_id=mesure.mesure_id,
        dispositif=mesure.dispositif,
        aide_loi_actuelle=aide_actuelle,
        aide_reforme=aide_reforme,
        ecart=ecart,
        statut="ok",
        trace=trace,
        empreinte=signature,
    )