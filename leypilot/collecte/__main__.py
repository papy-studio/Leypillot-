"""Outil en ligne de commande du lot 1 (essais à la main, sans base de données).

    python -m leypilot.collecte extraire donnees_exemple/lot1_corpus/an_I-2211.txt
    python -m leypilot.collecte jorf --fichier JORF_20261122-003012.tar.gz
    python -m leypilot.collecte jorf --depuis 2026-11-22          (télécharge)
    python -m leypilot.collecte an --fichier Amendements.json.zip
    python -m leypilot.collecte senat --session 2025-2026 --texte 138
    python -m leypilot.collecte bofip
    python -m leypilot.collecte piste                              (test de l'accès PISTE)

La tâche de nuit, elle, passe par ``depot.enregistrer_collecte`` (planificateur de P5).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

from leypilot.collecte.config import reglages_collecte
from leypilot.collecte.schemas import changements_du_texte
from leypilot.collecte.sources.base import Collecte
from leypilot.collecte.textes import normaliser


def _afficher(collectes: Iterable[Collecte]) -> int:
    code_retour = 0
    for collecte in collectes:
        controle = collecte.controle
        etat = "complet" if controle.complet else f"{len(controle.ecarts)} écart(s)"
        print(
            f"{collecte.source} {collecte.fichier} : {collecte.nb_lus} lus, "
            f"{len(collecte.documents)} dans le périmètre, contrôle {etat}"
        )
        for ecart in controle.ecarts[:20]:
            print(f"  ÉCART {ecart}")
        for document in collecte.documents:
            print(f"  - {document.identifiant} {document.titre or ''}"[:140])
        code_retour = code_retour or (0 if controle.complet else 2)
    return code_retour


def _extraire(chemin: Path) -> int:
    texte = normaliser(chemin.read_text(encoding="utf-8"))
    for changement in changements_du_texte(1, texte):
        print(
            json.dumps(changement.model_dump(mode="json", exclude={"cree_le"}), ensure_ascii=False)
        )
    return 0


def main(arguments: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="python -m leypilot.collecte")
    commandes = parseur.add_subparsers(dest="commande", required=True)
    extraire = commandes.add_parser("extraire", help="changements d'un texte (fichier .txt)")
    extraire.add_argument("chemin", type=Path)
    for nom in ("jorf", "an", "bofip"):
        sous = commandes.add_parser(nom)
        sous.add_argument("--fichier", type=Path)
        sous.add_argument("--depuis", type=date.fromisoformat, default=date.today() - timedelta(1))
    senat = commandes.add_parser("senat")
    senat.add_argument("--session", required=True, help="ex. 2025-2026")
    senat.add_argument("--texte", required=True, help="numéro du texte au Sénat, ex. 138")
    senat.add_argument("--commission", action="store_true")
    senat.add_argument("--fichier", type=Path)
    senat.add_argument("--depuis", type=date.fromisoformat, default=date(2000, 1, 1))
    commandes.add_parser("piste", help="teste l'accès à l'API Légifrance (secret jamais affiché)")
    args = parseur.parse_args(arguments)

    if args.commande == "extraire":
        return _extraire(args.chemin)
    reglages = reglages_collecte()
    brut = reglages.dossier_donnees_brutes
    if args.commande == "piste":
        from leypilot.collecte.sources.piste import ErreurPiste, tester_acces

        try:
            print(tester_acces(reglages))
        except ErreurPiste as erreur:
            print(f"Échec PISTE : {erreur}", file=sys.stderr)
            return 1
        return 0
    if args.commande == "jorf":
        from leypilot.collecte.sources import jorf

        if args.fichier:
            return _afficher([jorf.lire_fichier(args.fichier)])
        return _afficher(jorf.ConnecteurJORF(brut).recuperer(args.depuis))
    if args.commande == "an":
        from leypilot.collecte.sources import assemblee

        if args.fichier:
            return _afficher([assemblee.lire_archive(args.fichier, args.depuis)])
        return _afficher(assemblee.ConnecteurAN(brut).recuperer(args.depuis))
    if args.commande == "senat":
        from leypilot.collecte.sources import senat

        if args.fichier:
            return _afficher([senat.lire_fichier(args.fichier, args.session, args.texte)])
        connecteur = senat.ConnecteurSenat(brut, args.session, args.texte, args.commission)
        return _afficher(connecteur.recuperer(args.depuis))
    from leypilot.collecte.sources import bofip

    if args.fichier:
        return _afficher([bofip.lire_archive(args.fichier)])
    return _afficher(bofip.ConnecteurBOFiP(brut).recuperer(args.depuis))


if __name__ == "__main__":
    sys.exit(main())
