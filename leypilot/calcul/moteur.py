"""Moteur de calcul déterministe du lot 3 (P3). Le LLM n'intervient jamais ici."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal

from leypilot.calcul.interface import EtapeTrace, MesureChiffrable, ResultatSimulation
from leypilot.calcul.parametres import (
    charger,
    empreinte_regles,
    valeur_a_date,
    valeurs_avec_mesure,
    valeurs_sans_mesure,
)

VERSION_MOTEUR = "0.2.0"
DISPOSITIFS_GERES = ["CII"]  # CIR et JEI : sprint 2
CHAMPS_OBLIGATOIRES = {"CII": ["depenses_innovation", "effectif"]}
SOURCE_PROFIL = "profil client"
CENTIME = Decimal("0.01")


def euros(montant) -> Decimal:
    """Convertit en Decimal arrondi au centime (jamais de float pour de l'argent)."""
    return Decimal(str(montant)).quantize(CENTIME)


def calculer_cii(entrees: dict, p: dict, sources: dict) -> tuple[Decimal, list[EtapeTrace]]:
    """CII = min(dépenses, plafond) x taux, si l'entreprise est une PME."""
    depenses = euros(entrees["depenses_innovation"])
    effectif = Decimal(str(entrees["effectif"]))
    trace = [
        EtapeTrace(
            libelle="Dépenses d'innovation déclarées", valeur=depenses, source=SOURCE_PROFIL
        ),
        EtapeTrace(libelle="Effectif", valeur=effectif, source=SOURCE_PROFIL),
    ]
    if effectif >= p["seuil_effectif_pme"]:
        trace.append(
            EtapeTrace(
                libelle="Pas une PME : CII non applicable",
                valeur=euros(0),
                source=sources["seuil_effectif_pme"],
            )
        )
        return euros(0), trace

    plafond = euros(p["plafond_depenses"])
    assiette = min(depenses, plafond)
    montant = euros(assiette * p["taux"])
    trace += [
        EtapeTrace(
            libelle="Plafond des dépenses", valeur=plafond, source=sources["plafond_depenses"]
        ),
        EtapeTrace(libelle="Assiette retenue", valeur=assiette, source=sources["plafond_depenses"]),
        EtapeTrace(libelle="Taux appliqué", valeur=p["taux"], source=sources["taux"]),
        EtapeTrace(libelle="Crédit d'impôt innovation", valeur=montant, source=sources["taux"]),
    ]
    return montant, trace


FORMULES = {"CII": calculer_cii}


def empreinte(entrees: dict, mesure: MesureChiffrable, exercice: int, regles: str) -> str:
    """Mêmes entrées + même mesure + mêmes règles + même moteur = même empreinte."""
    contenu = json.dumps(
        [entrees, mesure.model_dump(mode="json"), exercice, regles, VERSION_MOTEUR],
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


def parametres_scenario(parametres: dict, mesure: MesureChiffrable, jour: date, avec_mesure: bool):
    """Valeur de chaque paramètre au jour donné, avec ou sans la mesure."""
    valeurs = {}
    for nom, parametre in parametres.items():
        serie = parametre["valeurs"]
        if nom == mesure.parametre:
            if avec_mesure:
                serie = valeurs_avec_mesure(serie, mesure.date_effet, mesure.nouvelle_valeur)
            else:
                serie = valeurs_sans_mesure(serie, mesure.date_effet)
        valeurs[nom] = valeur_a_date(serie, jour)
    return valeurs


def simuler_mesure(
    client_id: int, entrees: dict, mesure: MesureChiffrable, exercice: int
) -> ResultatSimulation:
    """Compare « loi sans la mesure » et « loi avec la mesure » pour un client.

    Supposition à valider avec l'expert : l'exercice est l'année civile.
    """
    vide = {
        "client_id": client_id,
        "mesure_id": mesure.mesure_id,
        "dispositif": mesure.dispositif,
        "aide_loi_actuelle": None,
        "aide_reforme": None,
        "ecart": None,
        "provisoire": not mesure.date_certaine,
    }

    if mesure.dispositif not in DISPOSITIFS_GERES:
        return ResultatSimulation(
            **vide,
            statut="impossible",
            motif=f"Dispositif {mesure.dispositif} pas encore géré par le moteur",
            empreinte=empreinte(entrees, mesure, exercice, ""),
        )

    parametres = charger(mesure.dispositif)
    signature = empreinte(entrees, mesure, exercice, empreinte_regles(mesure.dispositif))

    if mesure.parametre not in parametres:
        return ResultatSimulation(
            **vide,
            statut="impossible",
            motif=f"Paramètre inconnu : {mesure.parametre} (attendus : {', '.join(parametres)})",
            empreinte=signature,
        )

    manquants = [c for c in CHAMPS_OBLIGATOIRES[mesure.dispositif] if entrees.get(c) is None]
    if manquants:
        return ResultatSimulation(
            **vide,
            statut="impossible",
            motif="Profil client incomplet",
            champs_manquants=manquants,
            empreinte=signature,
        )

    debut, fin = date(exercice, 1, 1), date(exercice, 12, 31)
    if debut < mesure.date_effet <= fin:
        return ResultatSimulation(
            **vide,
            statut="en_attente",
            motif="Date d'effet en cours d'exercice : règle de prorata à confirmer avec l'expert",
            empreinte=signature,
        )

    sources = {nom: parametre["reference"] for nom, parametre in parametres.items()}
    formule = FORMULES[mesure.dispositif]
    sans = parametres_scenario(parametres, mesure, fin, avec_mesure=False)
    avec = parametres_scenario(parametres, mesure, fin, avec_mesure=True)
    aide_actuelle, trace_actuelle = formule(entrees, sans, sources)
    aide_reforme, trace_reforme = formule(entrees, avec, sources)

    chiffres = {
        "aide_loi_actuelle": aide_actuelle,
        "aide_reforme": aide_reforme,
        "ecart": aide_actuelle - aide_reforme,
    }
    return ResultatSimulation(
        **{**vide, **chiffres},
        statut="ok",
        trace_loi_actuelle=trace_actuelle,
        trace_reforme=trace_reforme,
        empreinte=signature,
    )
