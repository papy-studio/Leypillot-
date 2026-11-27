# Lot 1 · Collecter et détecter (personne 1)

Récupère chaque jour les textes officiels, garde ceux qui touchent le CIR, le CII ou la JEI, prouve qu'il n'en manque aucun (A1), et en extrait les **changements** (S2) : quel article, quelle valeur avant, quelle valeur après, avec le passage exact qui le prouve. Le lot 1 n'alimente que le lot 2 (cascade P1 → P2 → P3 → P4 → P5).

## Utilisation

Tâche de nuit (appelée par le planificateur de P5) :

```python
from datetime import date, timedelta
from leypilot.collecte.depot import enregistrer_collecte, pour_lot2
from leypilot.collecte.sources.jorf import ConnecteurJORF

for collecte in ConnecteurJORF(dossier_brut).recuperer(date.today() - timedelta(days=1)):
    enregistrer_collecte(session, collecte)  # documents, changements, contrôle
session.commit()  # le lot 1 ne fait jamais de commit

for document_filtre, changement_detecte in pour_lot2(session, dernier_id_traite):
    ...  # format de leypilot.mesure.entree (lot 2)
```

Essais à la main, sans base :

```bash
python -m leypilot.collecte extraire donnees_exemple/lot1_corpus/an_I-2211.txt
python -m leypilot.collecte jorf --fichier JORF_20261122-003012.tar.gz
python -m leypilot.collecte senat --session 2025-2026 --texte 138
python -m leypilot.collecte bofip
python -m leypilot.collecte piste        # test de l'accès PISTE, le secret n'est jamais affiché
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `sources/base.py` | Interface commune `recuperer(depuis)`, format `DocumentBrut`, téléchargement |
| `sources/jorf.py` | JO : archives quotidiennes de la DILA, sommaire et numéros de séquence |
| `sources/legi.py` | Codes consolidés (fonds LEGI de la DILA) : version actuelle des articles suivis |
| `sources/dila.py` | Outils communs aux fichiers XML de la DILA |
| `sources/assemblee.py` | Amendements de l'Assemblée nationale (archive JSON) |
| `sources/senat.py` | Amendements du Sénat (CSV « jeu complet ») |
| `sources/bofip.py` | Doctrine BOFiP (flux hebdomadaires numérotés, empreinte MD5) |
| `sources/piste.py` | Client de l'API Légifrance via PISTE (vérification ponctuelle, recours) |
| `textes.py` | Normalisation unique, empreintes `empreinte_texte` et `empreinte_etat` |
| `cibles.py` | Filtre large des documents, table cible (articles et subdivisions) |
| `formules.py` | Formules législatives (expressions régulières) et suivi des chapeaux |
| `schemas.py` | Format `Changement` et ses quatre règles de validation |
| `secours.py` | Lignes sans formule : « à revoir », lues par le LLM de secours si disponible |
| `comparaison_legi.py` | Écarts entre deux versions LEGI d'un article, confirmés par le JO |
| `completude.py` | Contrôle de complétude (A1) |
| `depot.py` | Enregistrement en base, versions, lecture pour le lot 2 |
| `vers_lot2.py` | Contrat 1 → 2 : `DocumentFiltre` et `ChangementDetecte` |
| `config.py` | Réglages lus dans le `.env` (PISTE, dossier des fichiers bruts) |

Tables (propriétaire P1, dans `leypilot/commun/modeles/collecte.py`) : `execution_collecte`, `document`, `cible`, `changement`. Pas de `mesure_id` dans `changement` : le lot 2 tient le lien dans `version_mesure`.

## Contrats avec les autres lots

**Comparaison LEGI.** Quand une nouvelle version d'un article suivi arrive, le lot 1 la compare à la précédente, mot à mot (un nombre et son unité comptent pour un mot). Chaque écart est confronté aux changements lus dans le texte du JO qui a modifié l'article : mêmes valeurs, il est confirmé ; sinon il part « à revoir » (`desaccord_legi`). Ces changements servent au contrôle et ne partent pas vers le lot 2.

**Secours LLM.** Une ligne qui nomme un article suivi sans formule reconnue (exemple réel : amendement Sénat I-1521, « Le taux de 30 % … est augmenté à due concurrence… ») devient un changement « à revoir ». Si la couche LLM de P2 répond, sa lecture est vérifiée mot pour mot (passage et valeurs) puis transmise avec `a_revoir` vrai ; une valeur absente du texte fait rejeter la lecture.

**Fournit à P2** (`vers_lot2.py`, `depot.pour_lot2`) les documents filtrés et les changements rattachés à un dispositif, au format de `leypilot/mesure/entree.py` :

- `texte_source` = `document.texte`, déjà normalisé : son SHA-256 est `document.empreinte_texte` ;
- les clauses d'application (« … s'applique aux dépenses exposées à compter du … ») partent dans `conditions`, telles quelles ;
- l'étape vient du type de texte (amendement : dépôt, texte adopté : adoption, loi : publication) ou du sort de l'amendement (adopté : `adoption` ; rejeté, tombé, retiré, non soutenu, irrecevable : `rejet`) ;
- quand seul l'état d'un document change, ses changements repartent rattachés à la nouvelle version : c'est ainsi que le lot 2 apprend l'adoption.

**Reçoit de P5** le planificateur (6 h chaque jour, 19 h pendant le budget), la base, l'accès réseau aux sites officiels et le rangement du secret PISTE. Détail dans `docs/conception/lot1_besoins_plateforme.pdf`.

## Tests

```bash
pytest tests/unitaires/collecte tests/fil_rouge/test_fil_rouge_lot1.py
```

Le fil rouge fait passer le vrai amendement I-2211, le texte adopté puis la loi publiée par le lot 1 puis par le `SuiviMesures` du lot 2 : une seule mesure CII, statuts proposée, votée, publiée, applicable au 1er janvier 2025.

Le test `test_format_attendu_par_entree_du_lot_2` s'exécute dès que `leypilot/mesure/entree.py` (branche de P2) est fusionné ; il est ignoré avant.

## Points ouverts

- **À vérifier sur de vraies archives DILA** : les lecteurs JO et LEGI sont testés sur des archives reconstituées. Avant la mise en service, lancer `python -m leypilot.collecte jorf --fichier <archive>` et `… legi --fichier <archive>` sur des archives réelles (le site de la DILA n'est pas joignable depuis l'environnement de développement de Claude).
- **Secours LLM** : branché sur `ServiceLLM` (prompt `s2_secours.v1`). Il ne s'active qu'une fois la requête au fournisseur écrite par Papy dans `ClientFournisseur` ; d'ici là, les lignes sans formule partent « à revoir » pour un humain.
- **LEGI** : seul le CGI est relié à son identifiant (`LEGITEXT000006069577`) ; ajouter le LPF quand son identifiant sera vérifié. Une première version reçue sert de référence : la création d'un article n'est donc pas encore signalée.
- **Source principale** : la répartition prévoit Légifrance via PISTE, le lot 1 propose les fichiers de la DILA (`docs/adr/0001-dila-source-principale.md`). Décision de groupe.
- **Type `version_consolidee`** (LEGI) : absent de `entree.TypeTexte` ; ces documents ne partent pas encore vers le lot 2.
- **Correspondance sort → étape** : proposition à valider avec P2.
- **Noms des paramètres** (taux du CII, plafond…) : à fixer par P3 ; d'ici là, `parametre` reprend l'objet de la formule (« taux », « année »).
