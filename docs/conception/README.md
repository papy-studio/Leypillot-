# Dossier de conception · Leypilot

Ce dossier décrit **ce que l'on construit avant de le coder** : les données (méthode Merise) et le comportement du logiciel (UML). Il découle du cahier des charges fonctionnel, du cahier technique et de la répartition en cinq lots.

## Sommaire

| N° | Document | Contenu | Méthode |
|---|---|---|---|
| 1 | [Acteurs et cas d'utilisation](01_cas_utilisation.md) | Qui utilise Leypilot et pour quoi faire ; fiches des cas principaux | UML · cas d'utilisation |
| 2 | [Dictionnaire des données](02_dictionnaire_donnees.md) | Chaque donnée : nom, signification, type, règle | Merise |
| 3 | [MCD](03_mcd.md) | Entités, associations, cardinalités, règles de gestion | Merise · niveau conceptuel |
| 4 | [MLD et contraintes](04_mld.md) | Tables, clés primaires et étrangères, contraintes SQL, propriétaire de chaque table | Merise · niveau logique |
| 5 | [Diagrammes de classes](05_classes.md) | Modèle du domaine, puis classes du lot 2 telles que codées | UML · classes, paquetages |
| 6 | [Diagrammes de séquence](06_sequences.md) | Tâche de nuit, résumé S3, décision du consultant, validation de l'expert | UML · séquence |
| 7 | [Diagrammes d'états](07_etats.md) | Cycle de vie : mesure, rattachement, règle proposée, alerte, action | UML · états-transitions |
| 8 | [Diagrammes d'activités](08_activites.md) | Rattachement A2, résumé S3, liste de la semaine | UML · activités |
| 9 | [Architecture](09_architecture.md) | Composants, déploiement, tâches planifiées | UML · composants, déploiement |

Ordre de lecture conseillé : 1 → 3 → 4 → 6 → 7. Le dictionnaire (2) sert de référence.

## Statut de chaque partie

| Partie | Statut |
|---|---|
| Lot 2 (mesure, résumé, couche LLM) | **Conforme au code** de `leypilot/mesure/` et `leypilot/commun/llm/` |
| Lots 1, 3, 4, 5 | **Proposition** tirée du cahier technique, à valider par le propriétaire de chaque lot |
| Schéma global | Tenu par la personne 5 ; ce dossier sert de base de discussion |

Les écarts entre la conception et le code actuel sont listés en fin de [MLD](04_mld.md#écarts-avec-le-code-actuel).

## Conventions

- **Noms** : en français, sans accent, en `minuscules_avec_soulignés` pour les tables et colonnes (comme dans le code).
- **MCD** : `#` devant l'identifiant d'une entité ; cardinalités Merise `(min,max)` écrites sur chaque patte d'association.
- **MLD** : clé primaire en **gras**, clé étrangère précédée de `#`.
- **Une table, un propriétaire** : seul le lot propriétaire écrit dans une table ; les autres la lisent.

## Lire les diagrammes

Les diagrammes sont écrits en [Mermaid](https://mermaid.js.org/), directement dans les fichiers Markdown :

- **GitHub** les affiche tels quels.
- **VS Code** : installer l'extension « Markdown Preview Mermaid Support », puis ouvrir l'aperçu (`Cmd+Maj+V`).
- **En ligne** : copier un bloc dans https://mermaid.live.

Un diagramme se modifie comme du texte, donc il se relit dans une pull request comme le code.

## Fil rouge

Chaque document illustre le cas du **client B** : le taux du CII passe de 30 % à 20 %, le client B a 400 000 € de dépenses éligibles, soit 40 000 € en jeu, à six semaines de l'échéance.
