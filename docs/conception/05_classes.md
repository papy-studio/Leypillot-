# 5 · Diagrammes de classes

Trois niveaux :

1. **Paquetages** : les modules Python et leurs dépendances.
2. **Modèle du domaine** : les objets métier, leurs attributs principaux et leurs opérations (toute la solution).
3. **Conception du lot 2** : les classes réellement codées dans `leypilot/mesure/` et `leypilot/commun/llm/`.

## 1 · Diagramme de paquetages

Une flèche signifie « dépend de » (importe ou lit les tables de).

```mermaid
flowchart TB
    subgraph web["web/ · React PWA · P5"]
        ecrans["Écrans consultant et expert"]
    end
    subgraph api["leypilot/api · FastAPI · P5"]
        routes["Routes, JWT, rôles"]
    end
    subgraph taches["leypilot/taches · APScheduler · P5"]
        planif["Tâches de nuit et du dimanche"]
    end
    subgraph metier["Modules métier"]
        collecte["leypilot/collecte · P1<br/>S1 S2 A1"]
        mesure["leypilot/mesure · P2<br/>S3 A2 à A5"]
        calcul["leypilot/calcul · P3<br/>S4 M1 à M6 G3"]
        alertes["leypilot/alertes · P4<br/>S5 G1 G2 G4"]
    end
    subgraph commun["leypilot/commun"]
        modeles["modeles · tables SQLAlchemy"]
        llm["llm · couche LLM · P2"]
        config["config, base · P5"]
    end
    openfisca["openfisca_leypilot · P3<br/>paramètres YAML, formules"]

    ecrans --> routes
    routes --> mesure
    routes --> calcul
    routes --> alertes
    planif --> collecte
    planif --> mesure
    planif --> calcul
    planif --> alertes
    collecte --> modeles
    mesure --> modeles
    calcul --> modeles
    alertes --> modeles
    collecte -. "secours S2" .-> llm
    mesure --> llm
    calcul -. "brouillon M3" .-> llm
    alertes -. "phrase G4" .-> llm
    calcul --> openfisca
    llm --> config
    modeles --> config
```

Règles de dépendance :

- un module métier **n'importe jamais un autre module métier** : il lit ses tables, ou une fonction de lecture publiée (`leypilot.mesure.requetes`) ;
- seule `leypilot/commun` est partagée ;
- l'API et les tâches sont les seuls points d'entrée.

## 2 · Modèle du domaine

```mermaid
classDiagram
    direction LR

    class Dispositif {
        <<enumeration>>
        CIR
        CII
        JEI
    }
    class StatutMesure {
        <<enumeration>>
        proposee
        votee
        publiee
        appliquee
        abandonnee
    }
    class Evenement {
        <<enumeration>>
        depot
        adoption
        publication
        entree_en_vigueur
        rejet
        suppression
        censure
    }
    class Role {
        <<enumeration>>
        consultant
        expert
    }

    class Document {
        +str source
        +str identifiant_officiel
        +str type_texte
        +date date_document
        +str empreinte_sha256
        +str chemin_fichier
        +bool dans_perimetre
    }
    class Changement {
        +Evenement evenement
        +Dispositif dispositif
        +str article_vise
        +str parametre
        +str ancienne_valeur
        +str nouvelle_valeur
        +str passage_cite
        +bool a_revoir
        +empreinte_texte() str
        +empreinte_changement() str
    }
    class Mesure {
        +Dispositif dispositif
        +str article_vise
        +str parametre
        +StatutMesure statut
        +list~str~ numeros_amendement
        +date date_entree_vigueur
        +NatureDate nature_date
        +bool a_revoir
        +niveau() Niveau
        +jours_restants(aujourd_hui) int
    }
    class TransitionMesure {
        +StatutMesure de_statut
        +StatutMesure vers_statut
        +Evenement evenement
        +date date_evenement
    }
    class Resume {
        +str texte
        +str citation
        +str methode
        +str version
        +bool a_verifier
        +list~str~ motifs_verification
    }
    class Client {
        +str raison_sociale
        +int effectif
        +bool est_pme
        +date date_creation
        +bool profil_complet
    }
    class Depense {
        +int annee
        +str categorie
        +Decimal montant
    }
    class Impact {
        +Decimal aide_exposee
        +Decimal ecart
        +str statut_chiffrage
        +bool profil_incomplet
        +montant_compare() Decimal
    }
    class Calcul {
        +str scenario
        +dict entrees
        +Decimal resultat
        +list trace
        +str commit_regles
        +rejouer() Decimal
    }
    class RegleProposee {
        +str parametre_openfisca
        +str nouvelle_valeur
        +date date_effet
        +str citation
        +str statut
        +valider(expert)
        +corriger(expert, valeur)
        +rejeter(expert, motif)
    }
    class Utilisateur {
        +str email
        +str nom
        +Role role
    }
    class ParametresConsultant {
        +Decimal seuil_urgence
        +Decimal poids_montant
        +Decimal poids_urgence
    }
    class Alerte {
        +Niveau niveau
        +bool urgente
        +StatutMesure etape
        +marquer_lue(utilisateur)
        +donner_avis(utile, motif)
    }
    class ActionType {
        +str code
        +str declencheur
        +str gabarit_phrase
    }
    class Action {
        +float score
        +str phrase
        +str statut
        +date echeance
        +accepter(motif)
        +reporter(date, motif)
        +rejeter(motif)
    }
    class JournalDecision {
        +str decision
        +str motif
        +str commit_regles
        +datetime decide_le
    }

    Document "1" -- "0..*" Changement : contient
    Changement "0..*" --> "1" Dispositif
    Mesure "1" o-- "1..*" Changement : regroupe
    Mesure "1" *-- "1..*" TransitionMesure : historique
    Changement "1" -- "0..*" Resume : résumé par
    Mesure "1" -- "0..*" Impact : touche
    Client "1" -- "0..*" Impact : touché par
    Client "1" *-- "0..*" Depense
    Client "0..*" --> "1" Utilisateur : consultant
    Impact "1" *-- "1..*" Calcul
    Mesure "1" -- "0..*" RegleProposee : fait proposer
    Impact "1" -- "0..1" Alerte
    Impact "1" -- "0..*" Action
    Action "0..*" --> "1" ActionType
    Action "1" *-- "0..*" JournalDecision
    Utilisateur "1" *-- "0..1" ParametresConsultant
```

Choix notables :

- **Composition** (losange plein) quand la partie n'existe pas sans le tout : une transition sans sa mesure, un calcul sans son impact, une entrée de journal sans son action.
- **Agrégation** (losange vide) entre mesure et changements : le changement appartient au lot 1 et existe avant d'être rattaché.
- Les opérations de `Action` (`accepter`, `reporter`, `rejeter`) écrivent toujours une `JournalDecision` ; il n'y a pas d'opération qui modifie le journal.

## 3 · Conception du lot 2 (classes codées)

Ce diagramme reflète le code de la branche `branche-Papy`. Les interfaces (`<<interface>>`) sont des `Protocol` Python : on peut remplacer leur réalisation sans toucher au reste (exigence « Remplacer »).

```mermaid
classDiagram
    direction TB

    class SuiviMesures {
        -Session session
        -ResumeurS3 resumeur
        -ServiceLLM service_llm
        +traiter(changement, mesure_imposee, forcer_nouvelle) ResultatTraitement
        +candidats(dispositif) list~CandidatMesure~
        +rattachements_en_attente() list~RattachementAValider~
        +confirmer_rattachement(attente_id) ResultatTraitement
        +refuser_rattachement(attente_id) ResultatTraitement
        +appliquer_entrees_en_vigueur(aujourd_hui) list~int~
        +relancer_resumes_en_attente() list~int~
    }
    class ResultatTraitement {
        +int changement_id
        +int mesure_id
        +bool nouvelle_mesure
        +StatutMesure statut
        +StatutMesure transition
        +int resume_id
        +DateVigueur date_vigueur
        +int en_attente_id
        +list~str~ erreurs
    }
    class ResumeurS3 {
        -Redacteur redacteur
        -SourceContexte contexte
        +version() str
        +resumer(changement, date_vigueur) ResumeProduit
    }
    class Redacteur {
        <<interface>>
        +str methode
        +str version
        +citer(changement, contexte) str
        +rediger(changement, citation, contexte, date_vigueur, regeneration) str
    }
    class RedacteurGabarit {
        +version = "gabarit.v1"
    }
    class RedacteurLLM {
        -ServiceLLM service
    }
    class SourceContexte {
        <<interface>>
        +texte_article(article) str
        +doctrine(dispositif) str
    }
    class ResumeProduit {
        +str texte
        +str citation
        +str methode
        +str version
        +list~str~ motifs
        +bool en_attente
        +a_verifier() bool
    }

    class ServiceLLM {
        -ClientLLM client
        -CacheLLM cache
        -int tentatives
        +generer(nom_prompt, schema, valeurs, version, forcer) T
    }
    class ClientLLM {
        <<interface>>
        +completer(requete) ReponseLLM
    }
    class ClientFournisseur {
        +completer(requete) ReponseLLM
    }
    class ClientFactice {
        +list appels
        +ajouter(tache, textes)
    }
    class ClientNonConfigure
    class CacheLLM {
        <<interface>>
        +lire(cle) ReponseLLM
        +ecrire(cle, requete, reponse)
    }
    class CacheMemoire
    class CacheBase {
        -Session session
    }
    class Prompt {
        +str nom
        +str version
        +str systeme
        +str message
        +requete(valeurs) RequeteLLM
    }

    class entree {
        <<module>>
        +assembler(changement_detecte, document) Changement
        +assembler_tous(documents, changements) list~Changement~
    }
    class requetes {
        <<module>>
        +mesures_modifiees_depuis(session, depuis) list~VueMesure~
        +mesures_publiees_depuis(session, depuis) list~Mesure~
        +vue_mesure(session, mesure_id) VueMesure
    }
    class rattachement {
        <<module>>
        +SEUIL_AUTO = 90
        +SEUIL_HUMAIN = 70
        +rattacher(changement, candidats) DecisionRattachement
        +score_similarite(changement, candidat) float
    }
    class etats {
        <<module>>
        +TRANSITIONS
        +statut_initial(evenement) StatutMesure
        +prochain_statut(statut, evenement) StatutMesure
    }
    class dates {
        <<module>>
        +dater(changement, date_publication, service_llm) DateVigueur
        +jours_restants(date, aujourd_hui) int
    }
    class graduation {
        <<module>>
        +niveau(statut) Niveau
        +verifier_action_autorisee(statut)
        +installer_contrainte_a5(connexion)
    }
    class anti_montant {
        <<module>>
        +montants_non_justifies(sortie, reference) list
        +chiffres_en_dur(texte) list
    }

    entree ..> SuiviMesures : Changement assemblé (P1 → P2)
    SuiviMesures ..> requetes : tables lues par P3
    SuiviMesures ..> rattachement : A2
    SuiviMesures ..> etats : A3
    SuiviMesures ..> dates : A4
    SuiviMesures --> ResumeurS3 : S3
    SuiviMesures ..> ResultatTraitement : produit
    ResumeurS3 --> Redacteur
    ResumeurS3 --> SourceContexte
    ResumeurS3 ..> ResumeProduit : produit
    ResumeurS3 ..> anti_montant
    Redacteur <|.. RedacteurGabarit
    Redacteur <|.. RedacteurLLM
    RedacteurLLM --> ServiceLLM
    dates ..> ServiceLLM : secours
    ServiceLLM --> ClientLLM
    ServiceLLM --> CacheLLM
    ServiceLLM ..> Prompt
    ClientLLM <|.. ClientFournisseur
    ClientLLM <|.. ClientFactice
    ClientLLM <|.. ClientNonConfigure
    CacheLLM <|.. CacheMemoire
    CacheLLM <|.. CacheBase
```

Points de conception :

- **Deux contrats, deux modules** : `entree` assemble ce que fournit la personne 1 (documents filtrés + changements détectés) ; `requetes` expose les mesures à la personne 3.
- **`SuiviMesures` est la façade** du lot : la tâche de nuit et l'API n'appellent qu'elle. Elle ne fait jamais de `commit` ; c'est l'appelant qui valide la transaction.
- **Le LLM est optionnel** : sans fournisseur configuré, `creer_resumeur` choisit `RedacteurGabarit` et les dates se lisent par expressions régulières.
- **`ClientFournisseur.completer`** est la seule méthode à écrire quand le fournisseur sera choisi ; tout le reste (cache, nouvelles tentatives, validation Pydantic, filtre anti-montant) est déjà en place.
