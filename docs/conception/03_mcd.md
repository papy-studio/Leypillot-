# 3 · Modèle conceptuel des données (MCD)

Le MCD décrit les données **indépendamment de la technique** : entités, associations entre elles et cardinalités. Il est lu dans le sens Merise : la cardinalité écrite près d'une entité dit combien de fois cette entité participe à l'association.

> Exemple : `CHANGEMENT (1,1) — PROVENIR — (0,n) DOCUMENT` se lit « un changement provient d'un et un seul document ; un document contient zéro, un ou plusieurs changements ».

Les 22 entités sont réparties en trois vues pour rester lisibles. Une entité grisée est détaillée dans une autre vue.

## Règles de gestion qui fondent le modèle

| N° | Règle | Traduction dans le MCD |
|---|---|---|
| R1 | Un document peut contenir plusieurs changements ; un changement vient d'un seul document. | PROVENIR (1,1)–(0,n) |
| R2 | Un changement touche un seul dispositif. | TOUCHER (1,1)–(0,n) |
| R3 | Une mesure regroupe toutes les versions d'une même modification (amendement, texte adopté, loi publiée). | COMPOSER (0,1)–(1,n) |
| R4 | Un changement ambigu n'est rattaché à aucune mesure tant qu'un humain n'a pas tranché. | COMPOSER côté changement en (0,1) ; RATTACHEMENT_A_VALIDER |
| R5 | Chaque changement de statut d'une mesure est journalisé avec son événement et sa date. | HISTORISER (1,1)–(1,n) |
| R6 | Un résumé décrit un changement, dans une version donnée du rédacteur. | RESUMER (1,1)–(0,n) |
| R7 | Un client est suivi par un seul consultant (portefeuille). | SUIVRE (1,1)–(0,n) |
| R8 | Une mesure touche zéro ou plusieurs clients ; pour chaque couple, un seul impact. | IMPACT relié à MESURE et CLIENT en (1,1) ; couple unique |
| R9 | Tout montant vient d'un calcul déterministe, versionné et rejouable. | CHIFFRER (1,1)–(0,n) |
| R10 | Une règle de calcul n'est utilisée qu'après validation par un expert. | VALIDER (0,1)–(0,n) |
| R11 | Une même mesure suivie dans plusieurs textes ne produit qu'une alerte par client. | SIGNALER (1,1)–(0,1) sur IMPACT |
| R12 | Une action n'est proposée que sur une mesure au moins votée (A5). | Contrainte sur RECOMMANDER, garantie en base |
| R13 | Toute décision du consultant est tracée : qui, quoi, quand, pourquoi. | DECIDER et AUTEUR (1,1)–(0,n) |
| R14 | Un consultant ne voit que les clients de son portefeuille. | Hérité de SUIVRE ; garanti par Row-Level Security |

## Vue 1 · Veille et suivi de la mesure (lots 1 et 2)

```mermaid
flowchart LR
    DISPOSITIF["<b>DISPOSITIF</b><br/>────────<br/>#code<br/>libelle<br/>article_cgi"]
    DOCUMENT["<b>DOCUMENT</b><br/>────────<br/>#id_document<br/>source<br/>identifiant_officiel<br/>type_texte<br/>titre<br/>date_document<br/>recu_le<br/>empreinte_sha256<br/>chemin_fichier<br/>dans_perimetre"]
    CIBLE["<b>CIBLE</b><br/>────────<br/>#id_cible<br/>type_cible<br/>valeur<br/>active"]
    CHANGEMENT["<b>CHANGEMENT</b><br/>────────<br/>#id_changement<br/>evenement<br/>date_document<br/>article_vise<br/>parametre<br/>ancienne_valeur<br/>nouvelle_valeur<br/>passage_cite<br/>methode_extraction<br/>a_revoir<br/>dossier_legislatif<br/>numero_amendement<br/>nor · eli"]
    MESURE["<b>MESURE</b><br/>────────<br/>#id_mesure<br/>article_vise<br/>parametre<br/>ancienne_valeur<br/>nouvelle_valeur<br/>conditions<br/>statut<br/>dossier_legislatif<br/>numeros_amendement<br/>nor · eli<br/>date_publication<br/>date_entree_vigueur<br/>nature_date<br/>clause_entree_vigueur<br/>a_revoir"]
    TRANSITION["<b>TRANSITION_MESURE</b><br/>────────<br/>#id_transition<br/>de_statut<br/>vers_statut<br/>evenement<br/>date_evenement"]
    RESUME["<b>RESUME</b><br/>────────<br/>#id_resume<br/>texte<br/>citation<br/>methode<br/>version<br/>empreinte_texte<br/>empreinte_changement<br/>a_verifier<br/>motifs_verification<br/>en_attente"]
    RATTACHEMENT["<b>RATTACHEMENT_A_VALIDER</b><br/>────────<br/>#id_rattachement<br/>score<br/>decision<br/>traite_le"]
    APPEL["<b>APPEL_LLM</b><br/>────────<br/>#cle<br/>tache<br/>version_prompt<br/>modele<br/>reponse<br/>jetons_entree<br/>jetons_sortie"]
    UTILISATEUR["UTILISATEUR<br/>(vue 3)"]

    PROVENIR(["PROVENIR"])
    TOUCHER(["TOUCHER"])
    VISER(["VISER"])
    COMPOSER(["COMPOSER<br/><i>methode, score,<br/>rattache_le</i>"])
    PORTER(["PORTER SUR"])
    HISTORISER(["HISTORISER"])
    DECLENCHER(["DÉCLENCHER"])
    RESUMER(["RÉSUMER"])
    DECRIRE(["DÉCRIRE"])
    PROPOSER_R(["SOUMETTRE"])
    CANDIDATER(["CANDIDATER"])
    TRANCHER(["TRANCHER"])

    CHANGEMENT ---|"1,1"| PROVENIR ---|"0,n"| DOCUMENT
    CHANGEMENT ---|"1,1"| TOUCHER ---|"0,n"| DISPOSITIF
    CIBLE ---|"1,1"| VISER ---|"0,n"| DISPOSITIF
    CHANGEMENT ---|"0,1"| COMPOSER ---|"1,n"| MESURE
    MESURE ---|"1,1"| PORTER ---|"0,n"| DISPOSITIF
    TRANSITION ---|"1,1"| HISTORISER ---|"1,n"| MESURE
    TRANSITION ---|"0,1"| DECLENCHER ---|"0,1"| CHANGEMENT
    RESUME ---|"1,1"| RESUMER ---|"0,n"| CHANGEMENT
    RESUME ---|"0,1"| DECRIRE ---|"0,n"| MESURE
    RATTACHEMENT ---|"1,1"| PROPOSER_R ---|"0,n"| CHANGEMENT
    RATTACHEMENT ---|"1,1"| CANDIDATER ---|"0,n"| MESURE
    RATTACHEMENT ---|"0,1"| TRANCHER ---|"0,n"| UTILISATEUR

    classDef entite fill:#e8f0fe,stroke:#1a56db,color:#0b1f4d,text-align:left
    classDef externe fill:#f1f1f1,stroke:#999,color:#555,stroke-dasharray:4 3
    classDef assoc fill:#fff8e1,stroke:#b7791f,color:#5a3e00
    class DISPOSITIF,DOCUMENT,CIBLE,CHANGEMENT,MESURE,TRANSITION,RESUME,RATTACHEMENT,APPEL entite
    class UTILISATEUR externe
    class PROVENIR,TOUCHER,VISER,COMPOSER,PORTER,HISTORISER,DECLENCHER,RESUMER,DECRIRE,PROPOSER_R,CANDIDATER,TRANCHER assoc
```

**Remarques**

- **MESURE est l'objet central** : elle naît du premier changement (dépôt d'un amendement) et rassemble les suivants (adoption, publication). Elle porte les identifiants officiels cumulés, et les valeurs et conditions du dernier texte : c'est ce que reçoit la personne 3 pour chiffrer.
- **COMPOSER** porte la manière dont le changement a été rattaché (par numéro d'amendement, par identifiant, par ressemblance, par un humain) et le score. Un changement non rattaché (0) est soit en attente dans RATTACHEMENT_A_VALIDER, soit un rejet sur une mesure inconnue.
- **DÉCLENCHER** est en (0,1) côté transition : le passage en « appliquée » vient de la date, pas d'un changement.
- **APPEL_LLM** n'est reliée à aucune entité : c'est le cache de la couche LLM, partagé par tous les lots. Elle ne contient que des textes publics.

## Vue 2 · Clients et chiffrage (lot 3)

```mermaid
flowchart LR
    DISPOSITIF["DISPOSITIF<br/>(vue 1)"]
    MESURE["MESURE<br/>(vue 1)"]
    UTILISATEUR["UTILISATEUR<br/>(vue 3)"]
    CLIENT["<b>CLIENT</b><br/>────────<br/>#id_client<br/>raison_sociale<br/>siren<br/>effectif<br/>chiffre_affaires<br/>est_pme<br/>date_creation<br/>profil_complet"]
    DEPENSE["<b>DEPENSE</b><br/>────────<br/>#id_depense<br/>annee<br/>categorie<br/>montant"]
    IMPACT["<b>IMPACT</b><br/>────────<br/>#id_impact<br/>aide_exposee<br/>ecart<br/>statut_chiffrage<br/>profil_incomplet<br/>piste_gain_net"]
    CALCUL["<b>CALCUL</b><br/>────────<br/>#id_calcul<br/>scenario<br/>entrees<br/>resultat<br/>trace<br/>commit_regles<br/>version_moteur<br/>empreinte"]
    REGLE["<b>REGLE_PROPOSEE</b><br/>────────<br/>#id_regle<br/>parametre_openfisca<br/>ancienne_valeur<br/>nouvelle_valeur<br/>date_effet<br/>citation<br/>reference_legifrance<br/>statut<br/>motif_expert<br/>commit_git"]

    SUIVRE(["SUIVRE"])
    UTILISER(["UTILISER<br/><i>depuis</i>"])
    ENGAGER(["ENGAGER"])
    RELEVER(["RELEVER DE"])
    CONCERNER_M(["CONCERNER"])
    CONCERNER_C(["AFFECTER"])
    CHIFFRER(["CHIFFRER"])
    SUGGERER(["SUGGÉRER"])
    DERIVER(["DÉRIVER DE"])
    VALIDER(["VALIDER"])

    CLIENT ---|"1,1"| SUIVRE ---|"0,n"| UTILISATEUR
    CLIENT ---|"0,n"| UTILISER ---|"0,n"| DISPOSITIF
    DEPENSE ---|"1,1"| ENGAGER ---|"0,n"| CLIENT
    DEPENSE ---|"1,1"| RELEVER ---|"0,n"| DISPOSITIF
    IMPACT ---|"1,1"| CONCERNER_M ---|"0,n"| MESURE
    IMPACT ---|"1,1"| CONCERNER_C ---|"0,n"| CLIENT
    CALCUL ---|"1,1"| CHIFFRER ---|"0,n"| IMPACT
    IMPACT ---|"0,1"| SUGGERER ---|"0,n"| DISPOSITIF
    REGLE ---|"1,1"| DERIVER ---|"0,n"| MESURE
    REGLE ---|"0,1"| VALIDER ---|"0,n"| UTILISATEUR

    classDef entite fill:#e8f0fe,stroke:#1a56db,color:#0b1f4d,text-align:left
    classDef externe fill:#f1f1f1,stroke:#999,color:#555,stroke-dasharray:4 3
    classDef assoc fill:#fff8e1,stroke:#b7791f,color:#5a3e00
    class CLIENT,DEPENSE,IMPACT,CALCUL,REGLE entite
    class DISPOSITIF,MESURE,UTILISATEUR externe
    class SUIVRE,UTILISER,ENGAGER,RELEVER,CONCERNER_M,CONCERNER_C,CHIFFRER,SUGGERER,DERIVER,VALIDER assoc
```

**Remarques**

- **IMPACT** aurait pu être une association porteuse entre MESURE et CLIENT. On en fait une entité parce que d'autres données s'y rattachent : les calculs, l'alerte, les actions.
- Un impact a en général **trois calculs** : loi actuelle, réforme, et éventuellement l'autre dispositif (piste G3). L'écart est la différence entre les deux premiers.
- **VALIDER** relie la règle à l'expert qui l'a tranchée ; (0,1) car la règle attend d'abord. Les règles validées vivent ensuite dans les fichiers YAML du dépôt Git, pas en base : seul le commit est gardé.

## Vue 3 · Alertes, actions et plateforme (lots 4 et 5)

```mermaid
flowchart LR
    IMPACT["IMPACT<br/>(vue 2)"]
    UTILISATEUR["<b>UTILISATEUR</b><br/>────────<br/>#id_utilisateur<br/>email<br/>nom<br/>role<br/>mot_de_passe_hache<br/>actif"]
    PARAMETRES["<b>PARAMETRES_CONSULTANT</b><br/>────────<br/>#id_parametres<br/>seuil_urgence<br/>poids_montant<br/>poids_urgence<br/>delai_relance_heures"]
    ABONNEMENT["<b>ABONNEMENT_PUSH</b><br/>────────<br/>#id_abonnement<br/>endpoint<br/>cle_p256dh<br/>cle_auth"]
    ALERTE["<b>ALERTE</b><br/>────────<br/>#id_alerte<br/>niveau<br/>urgente<br/>etape<br/>creee_le<br/>maj_le"]
    ACTION_TYPE["<b>ACTION_TYPE</b><br/>────────<br/>#id_action_type<br/>code<br/>declencheur<br/>libelle<br/>gabarit_phrase"]
    ACTION["<b>ACTION</b><br/>────────<br/>#id_action<br/>score<br/>detail_score<br/>phrase<br/>statut<br/>echeance<br/>reportee_au"]
    LISTE["<b>LISTE_SEMAINE</b><br/>────────<br/>#id_liste<br/>semaine<br/>generee_le"]
    JOURNAL["<b>JOURNAL_DECISION</b><br/>────────<br/>#id_entree<br/>decision<br/>motif<br/>reporte_au<br/>commit_regles<br/>decide_le"]

    REGLER(["RÉGLER"])
    ABONNER(["S'ABONNER"])
    SIGNALER(["SIGNALER"])
    DESTINER(["DESTINER À"])
    LIRE(["LIRE<br/><i>lu_le, relancee_le</i>"])
    AVISER(["AVISER<br/><i>utile, motif</i>"])
    RECOMMANDER(["RECOMMANDER"])
    INSTANCIER(["INSTANCIER"])
    FIGURER(["FIGURER<br/><i>rang, texte_ligne</i>"])
    RECEVOIR(["RECEVOIR"])
    DECIDER(["DÉCIDER"])
    AUTEUR(["ÉMETTRE"])

    PARAMETRES ---|"1,1"| REGLER ---|"0,1"| UTILISATEUR
    ABONNEMENT ---|"1,1"| ABONNER ---|"0,n"| UTILISATEUR
    ALERTE ---|"1,1"| SIGNALER ---|"0,1"| IMPACT
    ALERTE ---|"1,1"| DESTINER ---|"0,n"| UTILISATEUR
    ALERTE ---|"0,n"| LIRE ---|"0,n"| UTILISATEUR
    ALERTE ---|"0,n"| AVISER ---|"0,n"| UTILISATEUR
    ACTION ---|"1,1"| RECOMMANDER ---|"0,n"| IMPACT
    ACTION ---|"1,1"| INSTANCIER ---|"0,n"| ACTION_TYPE
    ACTION ---|"0,n"| FIGURER ---|"0,n"| LISTE
    LISTE ---|"1,1"| RECEVOIR ---|"0,n"| UTILISATEUR
    JOURNAL ---|"1,1"| DECIDER ---|"0,n"| ACTION
    JOURNAL ---|"1,1"| AUTEUR ---|"0,n"| UTILISATEUR

    classDef entite fill:#e8f0fe,stroke:#1a56db,color:#0b1f4d,text-align:left
    classDef externe fill:#f1f1f1,stroke:#999,color:#555,stroke-dasharray:4 3
    classDef assoc fill:#fff8e1,stroke:#b7791f,color:#5a3e00
    class UTILISATEUR,PARAMETRES,ABONNEMENT,ALERTE,ACTION_TYPE,ACTION,LISTE,JOURNAL entite
    class IMPACT externe
    class REGLER,ABONNER,SIGNALER,DESTINER,LIRE,AVISER,RECOMMANDER,INSTANCIER,FIGURER,RECEVOIR,DECIDER,AUTEUR assoc
```

**Remarques**

- **SIGNALER (1,1)–(0,1)** : un impact donne au plus une alerte. Quand la mesure avance (votée, puis publiée), la même alerte est mise à jour (`etape`, `maj_le`) au lieu d'en créer une nouvelle (R11).
- **DESTINER À** recopie le consultant du client. C'est une redondance voulue : la Row-Level Security filtre l'alerte sans jointure.
- **LIRE** et **AVISER** sont des associations porteuses : elles deviennent les tables `lecture_alerte` et `avis_alerte`.
- **RECOMMANDER** est soumise à R12 : le MCD ne sait pas exprimer « mesure au moins votée », c'est une contrainte d'intégrité ajoutée au MLD (trigger A5).
- **JOURNAL_DECISION** n'accepte que des ajouts : une décision n'est jamais modifiée, une nouvelle décision s'ajoute à la suite.

## Récapitulatif des associations

| Association | Entité A (card.) | Entité B (card.) | Données portées | Devient en MLD |
|---|---|---|---|---|
| PROVENIR | CHANGEMENT (1,1) | DOCUMENT (0,n) | | `changement.document_id` |
| TOUCHER | CHANGEMENT (1,1) | DISPOSITIF (0,n) | | `changement.dispositif` |
| VISER | CIBLE (1,1) | DISPOSITIF (0,n) | | `cible.dispositif` |
| COMPOSER | CHANGEMENT (0,1) | MESURE (1,n) | methode, score, rattache_le | table `version_mesure` |
| PORTER SUR | MESURE (1,1) | DISPOSITIF (0,n) | | `mesure.dispositif` |
| HISTORISER | TRANSITION_MESURE (1,1) | MESURE (1,n) | | `transition_mesure.mesure_id` |
| DÉCLENCHER | TRANSITION_MESURE (0,1) | CHANGEMENT (0,1) | | `transition_mesure.changement_id` |
| RÉSUMER | RESUME (1,1) | CHANGEMENT (0,n) | | `resume.changement_id` |
| DÉCRIRE | RESUME (0,1) | MESURE (0,n) | | `resume.mesure_id` |
| SOUMETTRE | RATTACHEMENT_A_VALIDER (1,1) | CHANGEMENT (0,n) | | `rattachement_a_valider.changement_id` |
| CANDIDATER | RATTACHEMENT_A_VALIDER (1,1) | MESURE (0,n) | | `rattachement_a_valider.mesure_candidate_id` |
| TRANCHER | RATTACHEMENT_A_VALIDER (0,1) | UTILISATEUR (0,n) | | `rattachement_a_valider.traite_par` |
| SUIVRE | CLIENT (1,1) | UTILISATEUR (0,n) | | `client.consultant_id` |
| UTILISER | CLIENT (0,n) | DISPOSITIF (0,n) | depuis | table `client_dispositif` |
| ENGAGER | DEPENSE (1,1) | CLIENT (0,n) | | `depense.client_id` |
| RELEVER DE | DEPENSE (1,1) | DISPOSITIF (0,n) | | `depense.dispositif` |
| CONCERNER | IMPACT (1,1) | MESURE (0,n) | | `impact.mesure_id` |
| AFFECTER | IMPACT (1,1) | CLIENT (0,n) | | `impact.client_id` |
| CHIFFRER | CALCUL (1,1) | IMPACT (0,n) | | `calcul.impact_id` |
| SUGGÉRER | IMPACT (0,1) | DISPOSITIF (0,n) | | `impact.piste_dispositif` |
| DÉRIVER DE | REGLE_PROPOSEE (1,1) | MESURE (0,n) | | `regle_proposee.mesure_id` |
| VALIDER | REGLE_PROPOSEE (0,1) | UTILISATEUR (0,n) | | `regle_proposee.expert_id` |
| RÉGLER | PARAMETRES_CONSULTANT (1,1) | UTILISATEUR (0,1) | | `parametres_consultant.consultant_id` (unique) |
| S'ABONNER | ABONNEMENT_PUSH (1,1) | UTILISATEUR (0,n) | | `abonnement_push.utilisateur_id` |
| SIGNALER | ALERTE (1,1) | IMPACT (0,1) | | `alerte.impact_id` (unique) |
| DESTINER À | ALERTE (1,1) | UTILISATEUR (0,n) | | `alerte.consultant_id` |
| LIRE | ALERTE (0,n) | UTILISATEUR (0,n) | lu_le, relancee_le | table `lecture_alerte` |
| AVISER | ALERTE (0,n) | UTILISATEUR (0,n) | utile, motif | table `avis_alerte` |
| RECOMMANDER | ACTION (1,1) | IMPACT (0,n) | | `action.impact_id` (+ `action.mesure_id` pour A5) |
| INSTANCIER | ACTION (1,1) | ACTION_TYPE (0,n) | | `action.action_type_id` |
| FIGURER | ACTION (0,n) | LISTE_SEMAINE (0,n) | rang, texte_ligne | table `ligne_liste` |
| RECEVOIR | LISTE_SEMAINE (1,1) | UTILISATEUR (0,n) | | `liste_semaine.consultant_id` |
| DÉCIDER | JOURNAL_DECISION (1,1) | ACTION (0,n) | | `journal_decision.action_id` |
| ÉMETTRE | JOURNAL_DECISION (1,1) | UTILISATEUR (0,n) | | `journal_decision.consultant_id` |
