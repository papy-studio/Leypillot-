# 2 · Dictionnaire des données

Chaque donnée manipulée par Leypilot, regroupée par entité. Les codes sont ceux des colonnes en base.

**Types** : `entier`, `décimal` (montant en euros, 2 décimales), `texte(n)` (n caractères au plus), `texte` (long), `date`, `horodatage` (date et heure avec fuseau), `booléen`, `liste` (JSON), `énum` (valeurs fixées, listées dans la colonne Règle).

Les identifiants techniques (`id`, entier auto-incrémenté) et les dates de création (`cree_le`) ne sont rappelés que lorsqu'ils ont un sens métier.

## Référentiel

### DISPOSITIF · *propriétaire P5 (schéma global)*

| Code | Signification | Type | Règle |
|---|---|---|---|
| `code` | Code du dispositif | énum | CIR, CII, JEI ; identifiant |
| `libelle` | Nom complet | texte(100) | « Crédit d'impôt innovation »… |
| `article_cgi` | Article du code général des impôts | texte(50) | 244 quater B (CIR, CII), 44 sexies-0 A (JEI) |

## Lot 1 · Collecter et détecter

### DOCUMENT

| Code | Signification | Type | Règle |
|---|---|---|---|
| `source` | Origine du texte | énum | legifrance, assemblee, senat, bofip |
| `identifiant_officiel` | Identifiant donné par la source | texte(200) | JORFTEXT…, n° de texte, n° d'amendement |
| `type_texte` | Nature du texte | énum | projet_loi, proposition_loi, amendement, texte_adopte, loi, version_consolidee, doctrine |
| `titre` | Intitulé | texte(500) | |
| `date_document` | Date portée par le texte | date | |
| `recu_le` | Heure de réception | horodatage | Horodatage S1 |
| `empreinte_sha256` | Empreinte du fichier brut | texte(64) | **Unique** : un texte déjà reçu n'est pas retraité |
| `chemin_fichier` | Emplacement du fichier brut sur disque | texte(500) | Version d'origine conservée |
| `dans_perimetre` | Retenu par le filtre de périmètre | booléen | Filtre large : un doute → vrai |

### CIBLE

| Code | Signification | Type | Règle |
|---|---|---|---|
| `type_cible` | Nature du critère | énum | article, mot_cle |
| `valeur` | Article ou mot-clé recherché | texte(200) | « 244 quater B », « jeune entreprise innovante » |
| `active` | Critère utilisé par le filtre | booléen | |

### CHANGEMENT

| Code | Signification | Type | Règle |
|---|---|---|---|
| `evenement` | Étape de procédure que porte le document | énum | depot, adoption, publication, entree_en_vigueur, rejet, suppression, censure |
| `date_document` | Date de l'étape | date | |
| `article_vise` | Article modifié | texte(300) | « article 244 quater B du code général des impôts » |
| `parametre` | Ce qui change | texte(300) | taux, plafond, date, condition |
| `ancienne_valeur` | Valeur avant | texte(200) | Vide si création |
| `nouvelle_valeur` | Valeur après | texte(200) | Vide si suppression |
| `passage_cite` | Passage exact du texte | texte | Doit figurer mot pour mot dans le texte source |
| `methode_extraction` | Comment le changement a été trouvé | énum | legi, regex, llm |
| `a_revoir` | Extraction non vérifiée | booléen | Vrai si une valeur ou la citation ne figure pas mot pour mot |
| `motif_a_revoir` | Raison du drapeau | texte | |
| `dossier_legislatif` | N° de dossier législatif | texte(200) | Identifiant officiel, sert au rattachement A2 |
| `numero_amendement` | N° d'amendement | texte(50) | Idem |
| `nor` | Identifiant NOR | texte(50) | Idem |
| `eli` | Identifiant ELI | texte(300) | Idem |

## Lot 2 · Comprendre et suivre la mesure

### MESURE

| Code | Signification | Type | Règle |
|---|---|---|---|
| `article_vise` | Article modifié par la mesure | texte(300) | Repris du premier changement |
| `parametre` | Paramètre modifié | texte(300) | Idem |
| `ancienne_valeur`, `nouvelle_valeur` | Valeurs avant et après | texte(200) | Reprises du **dernier** changement : le vote peut retenir une autre valeur que l'amendement ; la personne 3 en tire la réforme |
| `conditions` | Conditions d'application | liste | Union des conditions lues dans les changements (« PME »…) |
| `statut` | Étape de la mesure | énum | proposee, votee, publiee, appliquee, abandonnee ; voir [diagramme d'états](07_etats.md) |
| `dossier_legislatif` | N° de dossier législatif | texte(200) | Complété au fil des changements |
| `numeros_amendement` | Amendements qui portent la mesure | liste | Plusieurs amendements possibles |
| `nor`, `eli` | Identifiants du texte publié | texte | Connus à la publication |
| `date_publication` | Date de publication au JO | date | Renseignée à l'événement publication |
| `date_entree_vigueur` | Date d'application | date | Une date certaine n'est jamais écrasée par une estimation |
| `nature_date` | Fiabilité de la date | énum | certaine (lue dans le texte), estimee (déduite) |
| `clause_entree_vigueur` | Clause lue dans le texte | texte | « pour les dépenses exposées à compter du 1er janvier 2026 » |
| `a_revoir` | Incohérence à examiner | booléen | Vrai après une transition interdite |
| `motif_a_revoir` | Raison | texte | |

**Donnée calculée** (non stockée) : `jours_restants` = `date_entree_vigueur` − aujourd'hui ; `niveau` = information si statut proposee, action si votee, publiee ou appliquee.

### TRANSITION_MESURE

| Code | Signification | Type | Règle |
|---|---|---|---|
| `de_statut` | Statut avant | énum | Vide à la création |
| `vers_statut` | Statut après | énum | Doit figurer dans la table des transitions autorisées |
| `evenement` | Événement déclencheur | énum | Mêmes valeurs que `changement.evenement` |
| `date_evenement` | Date de l'événement | date | |

### VERSION_MESURE *(association COMPOSER)*

| Code | Signification | Type | Règle |
|---|---|---|---|
| `methode` | Comment le changement a été rattaché | énum | creation (première version), amendement, similarite, humain ; reprend `Methode` de `rattachement.py` |
| `score` | Score de ressemblance rapidfuzz | décimal | 0 à 100 ; vide si rattaché par identifiant |
| `document_id` | Document d'origine (lot 1) | entier | Lien de la mesure vers ses documents |
| `evenement`, `date_document` | Étape et date du document | énum, date | |
| `changement_json` | Copie du changement assemblé | texte | Permet de relancer un résumé sans relire le lot 1 |
| `rattache_le` | Heure du rattachement | horodatage | |

**Contrainte** : `changement_id` unique (un changement n'est rattaché qu'une fois).

### RESUME

| Code | Signification | Type | Règle |
|---|---|---|---|
| `texte` | Résumé en langage clair | texte | 3 à 5 phrases ; aucun montant absent de la citation |
| `citation` | Passage cité | texte | Vérifié mot pour mot |
| `methode` | Rédacteur | énum | llm, gabarit |
| `version` | Version du rédacteur et des prompts | texte(100) | « gabarit.v1 », « s3_resume.v1 » |
| `empreinte_texte` | SHA-256 du texte source | texte(64) | Clé de cache avec les deux suivantes |
| `empreinte_changement` | SHA-256 du changement (dont l'événement) | texte(64) | |
| `a_verifier` | Doute d'interprétation | booléen | Décret à paraître, extraction « à revoir », termes non définis |
| `motifs_verification` | Raisons du doute | liste | |
| `en_attente` | LLM en échec après ses nouvelles tentatives | booléen | Texte provisoire du gabarit ; relancé à la tâche suivante |

**Contrainte** : (`empreinte_texte`, `empreinte_changement`, `version`) unique.

### RATTACHEMENT_A_VALIDER

| Code | Signification | Type | Règle |
|---|---|---|---|
| `score` | Score de ressemblance | décimal | Entre 70 (`SEUIL_HUMAIN`) et 90 (`SEUIL_AUTO`) |
| `changement_json` | Copie du changement en attente | texte | Permet de le traiter sans relire le lot 1 |
| `decision` | Choix de l'humain | énum | confirme, refuse ; vide tant que non tranché |
| `traite_le` | Heure de la décision | horodatage | |

### APPEL_LLM *(cache et consommation de la couche LLM)*

| Code | Signification | Type | Règle |
|---|---|---|---|
| `cle` | Empreinte de la requête | texte(64) | **Unique** : SHA-256 de (tâche, version du prompt, système, message, modèle) |
| `tache` | Prompt utilisé | texte(50) | s3_citation, s3_resume, a4_date, puis ceux des autres lots |
| `version_prompt` | Version du prompt | texte(20) | v1… |
| `modele` | Modèle appelé | texte(100) | À choisir |
| `reponse` | Réponse brute validée | texte | Seules les réponses valides sont gardées |
| `jetons_entree`, `jetons_sortie` | Consommation | entier | Sert au suivi du budget |

## Lot 3 · Cibler et chiffrer

### CLIENT

| Code | Signification | Type | Règle |
|---|---|---|---|
| `raison_sociale` | Nom de l'entreprise | texte(200) | Fictif pour le MVP |
| `siren` | N° SIREN | texte(9) | Unique |
| `effectif` | Nombre de salariés | entier | |
| `chiffre_affaires` | Chiffre d'affaires annuel | décimal | |
| `est_pme` | Statut PME au sens européen | booléen | |
| `date_creation` | Date de création | date | Sert aux conditions d'âge de la JEI |
| `profil_complet` | Toutes les données de ciblage sont présentes | booléen | Faux → ciblé quand même, mention « profil incomplet » |

### UTILISER *(association client ↔ dispositif)*

| Code | Signification | Type | Règle |
|---|---|---|---|
| `depuis` | Première année d'utilisation | entier | |

### DEPENSE

| Code | Signification | Type | Règle |
|---|---|---|---|
| `annee` | Exercice | entier | |
| `categorie` | Catégorie de dépense éligible | texte(100) | Liste fixée par le dictionnaire client de l'expert |
| `montant` | Montant | décimal | ≥ 0 |

### IMPACT

| Code | Signification | Type | Règle |
|---|---|---|---|
| `aide_exposee` | Aide actuelle du client sur le dispositif touché | décimal | Affichée comme « aide exposée », jamais comme une perte |
| `ecart` | Écart loi actuelle contre réforme | décimal | Vide tant que la règle n'est pas validée (RG2) |
| `statut_chiffrage` | État du chiffrage | énum | en_attente_validation, chiffre, non_chiffrable |
| `profil_incomplet` | Ciblé malgré une donnée manquante | booléen | |
| `piste_gain_net` | Gain net de l'autre dispositif (G3) | décimal | « Piste à étudier », jamais une recommandation |

**Contrainte** : (`mesure_id`, `client_id`) unique.

### CALCUL

| Code | Signification | Type | Règle |
|---|---|---|---|
| `scenario` | Simulation effectuée | énum | loi_actuelle, reforme, autre_dispositif |
| `entrees` | Données du client utilisées | liste | Copie figée, pour rejouer le calcul |
| `resultat` | Montant de l'aide calculée | décimal | Seule source de montant de Leypilot |
| `trace` | Étapes du traceur OpenFisca | liste | Affichée en langage clair (M6) |
| `commit_regles` | Commit Git des règles utilisées | texte(40) | |
| `version_moteur` | Version d'OpenFisca et du paquet leypilot | texte(50) | |
| `empreinte` | SHA-256 de (entrées, commit, version) | texte(64) | Rejouer donne le même résultat |

### REGLE_PROPOSEE

| Code | Signification | Type | Règle |
|---|---|---|---|
| `parametre_openfisca` | Chemin du paramètre | texte(200) | `cii.taux` |
| `ancienne_valeur`, `nouvelle_valeur` | Valeurs | texte(100) | |
| `date_effet` | Date d'effet de la nouvelle valeur | date | |
| `citation` | Passage exact de la loi | texte | Obligatoire (M3) |
| `reference_legifrance` | Lien vers l'article | texte(300) | |
| `statut` | État de la proposition | énum | en_attente, validee, corrigee, rejetee |
| `motif_expert` | Raison d'une correction ou d'un rejet | texte | |
| `commit_git` | Commit qui a écrit le YAML | texte(40) | Renseigné à la validation |

## Lot 4 · Alerter et agir

### PARAMETRES_CONSULTANT

| Code | Signification | Type | Règle |
|---|---|---|---|
| `seuil_urgence` | Montant au-delà duquel une alerte est urgente | décimal | Valeur par défaut à fixer avec Leyton |
| `poids_montant`, `poids_urgence` | Poids du score de priorité | décimal | |
| `delai_relance_heures` | Délai avant relance d'une alerte urgente non lue | entier | Une seule relance |

### ALERTE

| Code | Signification | Type | Règle |
|---|---|---|---|
| `niveau` | Information ou action | énum | Reprend le niveau A5 de la mesure |
| `urgente` | Montant ≥ seuil du consultant | booléen | Urgente → Web Push ; sinon liste de la semaine |
| `etape` | Statut de la mesure au dernier envoi | énum | Une alerte par mesure et par client, mise à jour à chaque étape |
| `maj_le` | Dernière mise à jour | horodatage | |

### LECTURE_ALERTE *(association LIRE)*

| Code | Signification | Type | Règle |
|---|---|---|---|
| `lu_le` | Heure du clic « Lu » | horodatage | Vide = non lue |
| `relancee_le` | Heure de la relance | horodatage | |

### AVIS_ALERTE *(association AVISER)*

| Code | Signification | Type | Règle |
|---|---|---|---|
| `utile` | Avis du consultant | booléen | Indicateur « part des alertes jugées utiles » |
| `motif` | Raison facultative | texte | |

### ACTION_TYPE

| Code | Signification | Type | Règle |
|---|---|---|---|
| `code` | Code de l'action type | texte(50) | Unique |
| `declencheur` | Situation qui l'appelle | énum | mesure_votee, aide_reduite, date_proche |
| `libelle` | Action concrète | texte(200) | « Prendre rendez-vous avec le client » |
| `gabarit_phrase` | Phrase avec emplacements | texte | `{montant}`, `{delai}` remplis par le moteur, jamais par le LLM |

### ACTION

| Code | Signification | Type | Règle |
|---|---|---|---|
| `score` | Score de priorité | décimal | Montant normalisé × facteur d'urgence (G1) |
| `detail_score` | Décomposition du score | liste | Affichée pour expliquer le classement |
| `phrase` | Recommandation rédigée | texte | Aucun chiffre en dur produit par le LLM |
| `statut` | État de l'action | énum | proposee, acceptee, reportee, rejetee |
| `echeance` | Date limite pour agir | date | = date d'entrée en vigueur de la mesure |
| `reportee_au` | Date de retour dans la liste | date | Si reportée |

**Contrainte A5** : la mesure de l'action est au moins votée (trigger PostgreSQL).

### LISTE_SEMAINE et LIGNE_LISTE *(association FIGURER)*

| Code | Signification | Type | Règle |
|---|---|---|---|
| `semaine` | Lundi de la semaine visée | date | Unique par consultant |
| `generee_le` | Heure de génération | horodatage | Dimanche soir |
| `rang` | Position de l'action dans la liste | entier | |
| `texte_ligne` | Ligne rédigée par gabarit Jinja2 | texte | « Client B, 40 000 € en jeu, six semaines, rendez-vous cette semaine » |

## Lot 5 · Plateforme

### UTILISATEUR

| Code | Signification | Type | Règle |
|---|---|---|---|
| `email` | Identifiant de connexion | texte(200) | Unique |
| `nom` | Nom affiché | texte(200) | |
| `role` | Rôle | énum | consultant, expert ; pas de rôle manager |
| `mot_de_passe_hache` | Mot de passe haché | texte(200) | Jamais en clair |
| `actif` | Compte utilisable | booléen | |

### ABONNEMENT_PUSH

| Code | Signification | Type | Règle |
|---|---|---|---|
| `endpoint` | Adresse du service push du navigateur | texte(500) | Unique |
| `cle_p256dh`, `cle_auth` | Clés de chiffrement Web Push | texte(200) | |

### JOURNAL_DECISION

| Code | Signification | Type | Règle |
|---|---|---|---|
| `decision` | Choix du consultant | énum | accepter, reporter, rejeter |
| `motif` | Pourquoi | texte | **Obligatoire** |
| `reporte_au` | Date choisie si report | date | |
| `commit_regles` | Commit des règles qui ont produit le chiffre | texte(40) | |
| `decide_le` | Quand | horodatage | |

**Contrainte** : ajout seul ; un trigger refuse toute modification ou suppression (G6).
