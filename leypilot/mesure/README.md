# Lot 2 · Comprendre et suivre la mesure (personne 2)

Transforme chaque changement détecté par le lot 1 en **mesure** suivie : rattachée aux versions précédentes (A2), qualifiée par son statut (A3), datée (A4), résumée (S3), et protégée contre toute action prématurée (A5). Fournit aussi la **couche LLM** partagée (`leypilot/commun/llm/`).

## Utilisation

```python
from datetime import date
from leypilot.mesure.entree import assembler_tous
from leypilot.mesure.suivi import SuiviMesures

# Ce que fournit la personne 1 : documents filtrés et changements détectés.
changements, erreurs = assembler_tous(documents_filtres, changements_detectes)

suivi = SuiviMesures(session)  # résumés par gabarit, sans LLM
for changement in changements:
    suivi.traiter(changement)
suivi.relancer_resumes_en_attente()  # résumés laissés en attente par une panne du LLM
suivi.appliquer_entrees_en_vigueur(date.today())
session.commit()  # le suivi ne fait jamais de commit
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `entree.py` | Contrat d'entrée P1 → P2 : `DocumentFiltre`, `ChangementDetecte`, assemblage en `Changement` |
| `schemas.py` | Types (`StatutMesure`, `Evenement`…) et `Changement`, le format de travail du lot |
| `suivi.py` | Chaîne complète, point d'entrée de la tâche de nuit |
| `rattachement.py` | A2 : numéro d'amendement, puis `rapidfuzz` sur article et paramètre |
| `etats.py` | A3 : machine à états et table des transitions autorisées |
| `dates.py` | A4 : clauses d'entrée en vigueur, secours LLM, droit commun, compte à rebours |
| `graduation.py`, `sql/` | A5 : niveau information ou action, trigger PostgreSQL sur `action` |
| `resume.py` | S3 : citation vérifiée, rédaction (gabarit ou LLM), filtre anti-montant |
| `drapeaux.py` | Drapeau « à vérifier » : décret à paraître, extraction à revoir, termes non définis |
| `contexte.py` | Contexte du résumé, retrouvé par identifiant d'article |
| `requetes.py` | Contrat de sortie P2 → P3 : `mesures_modifiees_depuis`, `mesures_publiees_depuis`, `vue_mesure` |
| `textes.py` | Normalisation, vérification mot pour mot, identifiants d'article, dates en français |

Tables (propriétaire P2, dans `leypilot/commun/modeles/`) : `mesure`, `version_mesure`, `transition_mesure`, `resume`, `rattachement_a_valider`, `appel_llm`.

## Contrats avec les autres lots

Les données descendent en cascade : P1 → P2 → P3 → P4 → P5. Le lot 2 lit seulement ce que produit la personne 1 et ne transmet qu'à la personne 3.

**Reçoit de P1** (contrat provisoire, à valider ensemble, `entree.py`) :

- des **documents filtrés** (`DocumentFiltre`) : identifiant, source, type de texte (amendement, texte adopté, loi…), date, texte complet, identifiants officiels (dossier législatif, n° d'amendement, NOR, ELI), étape explicite si besoin (rejet, censure) ;
- des **changements détectés** (`ChangementDetecte`) : document d'origine, dispositif, paramètre, ancienne et nouvelle valeur, passage cité, et en option l'article visé, les conditions et le drapeau « à revoir ».

L'étape de procédure se déduit du type de texte ; l'article visé, du texte s'il n'est pas fourni. `assembler_tous` met les changements dans l'ordre de la procédure et écarte ceux dont le document manque.

**Fournit à P3** (`requetes.py`) :

- `mesures_modifiees_depuis(session, depuis)` : les mesures à (re)chiffrer, avec dispositif, article, paramètre, ancienne et nouvelle valeur, conditions, statut, niveau (information ou action), dates de publication et d'entrée en vigueur (certaine ou estimée), jours restants, résumé, citation, drapeaux, documents d'origine ;
- `mesures_publiees_depuis(session, depuis)` : les mesures publiées au JO, déclencheur de M3 ;
- `vue_mesure(session, mesure_id)` : une mesure (sert aussi à l'historique affiché par P5).

P3 transmet à P4 ce qu'il lui faut (niveau, date, résumé) avec les impacts. `Mesure.id` reste la clé de regroupement des alertes.

**Demande à P4** une colonne `mesure_id` sur la table `action`, puis l'appel de `installer_contrainte_a5(connexion)` dans la migration qui crée cette table.

**Fournit à tous** `ServiceLLM` : `service.generer("nom_du_prompt", Schema, {"variable": valeur, ...})`.

## LLM

La répartition retient Claude (seul modèle pour le MVP, sans secours) ; la requête au fournisseur reste à écrire dans `ClientFournisseur.completer` (`leypilot/commun/llm/client.py`). Sans `LLM_FOURNISSEUR` dans le `.env`, tout fonctionne sans LLM : résumés par gabarit, dates par expressions régulières. Les tests utilisent `ClientFactice`.

Gestion des erreurs : chaque appel est retenté une fois (`ServiceLLM(tentatives=2)`). Si le LLM échoue encore, le résumé est enregistré **en attente** avec le texte du gabarit, pour que le consultant ait déjà une information ; `relancer_resumes_en_attente()` le refait à la tâche suivante.

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
