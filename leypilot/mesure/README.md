# Lot 2 · Comprendre et suivre la mesure (personne 2)

Transforme chaque changement détecté par le lot 1 en **mesure** suivie : rattachée aux versions précédentes (A2), qualifiée par son statut (A3), datée (A4), résumée (S3), et protégée contre toute action prématurée (A5). Fournit aussi la **couche LLM** partagée (`leypilot/commun/llm/`).

## Utilisation

```python
from datetime import date
from leypilot.mesure.suivi import SuiviMesures

suivi = SuiviMesures(session)  # résumés par gabarit, sans LLM
for changement in changements:  # objets Changement reçus du lot 1
    suivi.traiter(changement)
suivi.appliquer_entrees_en_vigueur(date.today())
session.commit()  # le suivi ne fait jamais de commit
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `schemas.py` | Types (`StatutMesure`, `Evenement`…) et contrat d'entrée `Changement` |
| `suivi.py` | Chaîne complète, point d'entrée de la tâche de nuit |
| `rattachement.py` | A2 : numéro d'amendement, puis `rapidfuzz` sur article et paramètre |
| `etats.py` | A3 : machine à états et table des transitions autorisées |
| `dates.py` | A4 : clauses d'entrée en vigueur, secours LLM, droit commun, compte à rebours |
| `graduation.py`, `sql/` | A5 : niveau information ou action, trigger PostgreSQL sur `action` |
| `resume.py` | S3 : citation vérifiée, rédaction (gabarit ou LLM), filtre anti-montant |
| `drapeaux.py` | Drapeau « à vérifier » : décret à paraître, extraction à revoir, termes non définis |
| `contexte.py` | Contexte du résumé, retrouvé par identifiant d'article |
| `requetes.py` | Lectures pour les lots 3 et 4 |
| `textes.py` | Normalisation, vérification mot pour mot, identifiants d'article, dates en français |

Tables (propriétaire P2, dans `leypilot/commun/modeles/`) : `mesure`, `transition_mesure`, `resume`, `rattachement_a_valider`, `appel_llm`.

## Contrats avec les autres lots

**Reçoit de P1** un `Changement` (contrat provisoire, à valider ensemble) : identifiant, document, étape de procédure (`evenement`), date du document, dispositif, article visé, paramètre, ancienne et nouvelle valeur, passage cité, texte complet, drapeau « à revoir », identifiants officiels (dossier législatif, n° d'amendement, NOR, ELI).

**Fournit à P3** `mesures_publiees_depuis(session, depuis)` : les mesures publiées au JO, déclencheur de M3.

**Fournit à P4** `vue_mesure(session, mesure_id)` : statut, niveau (information ou action), date d'entrée en vigueur certaine ou estimée, jours restants, résumé, citation, drapeaux. `Mesure.id` sert de clé de regroupement des alertes.

**Demande à P4** une colonne `mesure_id` sur la table `action`, puis l'appel de `installer_contrainte_a5(connexion)` dans la migration qui crée cette table.

**Fournit à tous** `ServiceLLM` : `service.generer("nom_du_prompt", Schema, {"variable": valeur, ...})`.

## LLM

Le fournisseur n'est pas choisi. Sans `LLM_FOURNISSEUR` dans le `.env`, tout fonctionne sans LLM : résumés par gabarit, dates par expressions régulières. La requête au fournisseur reste à écrire dans `ClientFournisseur.completer` (`leypilot/commun/llm/client.py`). Les tests utilisent `ClientFactice`.

## Tests

```bash
pytest tests/unitaires/mesure tests/unitaires/commun_llm tests/fil_rouge
```

Le test du trigger A5 sur PostgreSQL se lance avec `LEYPILOT_TEST_POSTGRES_URL=postgresql+psycopg://…/base_de_test` (la base est vidée).

## Points ouverts

- Statut « En attente de décret » quand la loi renvoie à un décret, et cycle propre au BOFiP (consultation, publication) : à ajouter dans `etats.py`.
- Seuils de rattachement (`SEUIL_AUTO` = 90, `SEUIL_HUMAIN` = 70) à calibrer sur de vrais textes.
- Implémentation de `SourceContexte` en base, quand les tables du lot 1 existeront.
- Une mesure abandonnée après la création d'une action : comportement à définir avec P4.
