# Contribuer à Leypilot

## Branches

- `main` est protégée : on n'y pousse jamais directement.
- Une branche par tâche, préfixée par le lot : `p1/connecteur-legifrance`, `p2/machine-etats-mesure`, `p5/auth-jwt`…
- Chaque branche aboutit à une pull request vers `main`.

## Qui modifie quoi

- Chacun ne modifie que les dossiers de son lot (voir le tableau du README).
- Une table, un propriétaire : seul le lot propriétaire écrit dans sa table, les autres la lisent.
- Toute modification de `leypilot/commun/` ou de `migrations/` passe par une pull request relue par la personne 5.
- Toute évolution du schéma de la base passe par une migration Alembic.

## Pull requests

- Au moins une relecture par une autre personne avant la fusion.
- L'intégration continue (ruff + pytest) doit être verte.
- La description dit ce qui change, pourquoi, et comment le tester.

## Messages de commit

Forme courte, au présent, avec le lot en préfixe :

```
p2: ajoute la machine à états de la mesure
p4: corrige le calcul du score de priorité
```

## Définition de « terminé »

Une tâche est terminée quand :

1. le code est relu et fusionné dans `main` ;
2. les tests unitaires du lot passent et couvrent le cas nominal et au moins un cas d'erreur ;
3. le scénario du client B fonctionne toujours ;
4. la documentation est à jour (README du lot, ADR si un choix d'architecture a été fait).

## Secrets

Aucune clé dans Git. Les clés (PISTE, Mistral, Claude, VAPID, JWT) vont dans `.env`, qui est ignoré. Ajouter toute nouvelle variable à `.env.example` sans sa valeur.

## Décisions d'architecture

Chaque choix important s'écrit dans `docs/adr/` en un fichier numéroté (`0001-openfisca-ou-plan-b.md`) : contexte, décision, alternatives, conséquences. Modèle : `docs/adr/0000-modele.md`.
