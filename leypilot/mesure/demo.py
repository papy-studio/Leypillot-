"""Démonstration du lot 2 sur le fil rouge du client B (base SQLite en mémoire).

python -m leypilot.mesure.demo
"""

import json
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import leypilot.commun.modeles  # noqa: F401
from leypilot.commun.base import Base
from leypilot.commun.llm import ClientFactice, ServiceLLM
from leypilot.commun.modeles.mesure import Mesure
from leypilot.mesure.dates import dater
from leypilot.mesure.graduation import ActionInterdite, verifier_action_autorisee
from leypilot.mesure.requetes import vue_mesure
from leypilot.mesure.resume import creer_resumeur
from leypilot.mesure.schemas import Changement, StatutMesure
from leypilot.mesure.suivi import SuiviMesures

FICHIER = Path(__file__).parents[2] / "donnees_exemple" / "lot2_client_b.json"


def titre(texte: str) -> None:
    print(f"\n=== {texte} " + "=" * max(0, 70 - len(texte)))


def afficher(session: Session, mesure_id: int, aujourd_hui: date) -> None:
    vue = vue_mesure(session, mesure_id, aujourd_hui)
    if vue is None:
        print(f"  Mesure n° {mesure_id} introuvable")
        return
    print(f"  Mesure n° {vue.id} : statut {vue.statut}, niveau {vue.niveau}")
    print(
        f"  Entrée en vigueur : {vue.date_entree_vigueur} ({vue.nature_date}), "
        f"dans {vue.jours_restants} jours"
    )
    print(f"  Résumé : {vue.resume}")
    print(f"  Citation : {vue.citation}")
    print(f"  À vérifier : {'oui' if vue.a_verifier else 'non'}")


def main() -> None:
    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    aujourd_hui = date.fromisoformat(donnees["aujourd_hui"])
    changements = [Changement.model_validate(c) for c in donnees["changements"]]

    moteur = create_engine("sqlite://")
    Base.metadata.create_all(moteur)
    with Session(moteur) as session:
        suivi = SuiviMesures(session)
        mesure_id: int | None = None
        for changement in changements:
            titre(
                f"{changement.evenement} du {changement.date_document} ({changement.article_vise})"
            )
            resultat = suivi.traiter(changement)
            if resultat.mesure_id is None:
                print(f"  Aucune mesure : {resultat.erreurs or 'rattachement en attente'}")
                continue
            mesure_id = resultat.mesure_id
            if resultat.nouvelle_mesure:
                print("  Nouvelle mesure")
            else:
                print("  Rattaché à la mesure existante")
            afficher(session, mesure_id, aujourd_hui)

        titre("A5 : peut-on créer une action ?")
        for statut in (StatutMesure.PROPOSEE, StatutMesure.VOTEE):
            try:
                verifier_action_autorisee(statut)
                print(f"  Mesure {statut} : action autorisée")
            except ActionInterdite as erreur:
                print(f"  Mesure {statut} : {erreur}")

        titre("1er janvier 2026 : entrée en vigueur")
        suivi.appliquer_entrees_en_vigueur(date(2026, 1, 1))
        mesure = session.get(Mesure, mesure_id) if mesure_id is not None else None
        if mesure is not None:
            parcours = " → ".join(t.vers_statut for t in mesure.transitions)
            print(f"  Parcours : {parcours}")

    titre("S3 : un LLM qui invente un montant")
    llm = ClientFactice(
        {
            "s3_citation": [
                '{"citation": "le taux : « 30 % » est remplacé par le taux : « 20 % »"}'
            ],
            "s3_resume": [
                '{"resume": "Le client B perd 40 000 € par an."}',
                '{"resume": "Toujours 40 000 € de perte."}',
            ],
        }
    )
    resumeur = creer_resumeur(ServiceLLM(llm))
    produit = resumeur.resumer(changements[0], dater(changements[0]))
    print("  Réponses du LLM : « 40 000 € » deux fois, absent de la citation")
    print(f"  Résumé retenu ({produit.methode}) : {produit.texte}")


if __name__ == "__main__":
    main()
