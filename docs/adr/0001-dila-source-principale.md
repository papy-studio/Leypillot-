# ADR 0001 · Fichiers de la DILA comme source principale du JO et des codes

- **Date :** 2026-11-27
- **Statut :** proposée
- **Auteur :** Personne 1 (Jay, DONZO)

## Contexte

Le lot 1 doit récupérer chaque jour le Journal officiel et les articles des codes (CGI, LPF) qui portent le CIR, le CII et la JEI, et prouver qu'aucun texte ne manque. La répartition prévoit « Légifrance via PISTE ». Deux accès existent pour les mêmes données :

- l'API Légifrance via PISTE : compte, jeton OAuth2 valable une heure, quota de 20 requêtes par seconde, un appel par texte ou par article ;
- l'open data de la DILA (https://echanges.dila.gouv.fr/OPENDATA/) : une archive par publication (fonds JORF et LEGI), sans compte, avec le sommaire de chaque numéro du JO.

## Décision

Pour le MVP, le JO et les codes sont lus dans les archives de la DILA. PISTE sert à vérifier un article précis et de recours si une archive manque. Le compte PISTE existe (titulaire : P1) et a été testé.

## Alternatives étudiées

- **PISTE seul.** Avantages : données à jour à la minute, recherche par article. Inconvénients : un appel par texte, quota, jeton à renouveler, secret à protéger dans la tâche de nuit ; aucune liste complète des textes d'un numéro du JO, donc pas de preuve de complétude simple.
- **DILA seule.** Avantages : tout le numéro en un fichier, sommaire (JORFCONT) et numéros de séquence pour le contrôle de complétude, fichiers bruts conservés tels quels. Inconvénients : publication en lots (vers 0 h 30 et 21 h), archives à décompresser.

## Conséquences

- Le contrôle de complétude compare le sommaire du JO aux textes reçus (essai sur le JO n° 273 du 22 novembre 2026 : 65 textes annoncés, 65 reçus).
- La tâche de nuit n'a pas besoin du secret PISTE ; il ne sert que pour les vérifications.
- Le dossier des fichiers bruts (`donnees_brutes/`, hors Git) prend environ 3 Go au démarrage.
- Si le groupe préfère PISTE, `leypilot/collecte/sources/piste.py` fournit déjà le client ; il faudra écrire un connecteur `recuperer(depuis)` qui l'utilise.
