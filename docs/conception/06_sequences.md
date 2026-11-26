# 6 · Diagrammes de séquence

Quatre scénarios, du plus général au plus précis. Tous suivent le **client B**.

## 1 · La tâche de nuit, de bout en bout

Chaque nuit, le planificateur enchaîne les lots dans l'ordre de la cascade P1 → P2 → P3 → P4. Chaque module lit les tables du précédent et écrit les siennes ; ils ne s'appellent jamais directement.

```mermaid
sequenceDiagram
    autonumber
    participant H as Planificateur
    participant C as Collecte P1
    participant S as Sources officielles
    participant M as SuiviMesures P2
    participant K as Calcul P3
    participant A as Alertes P4
    participant DB as PostgreSQL
    participant WP as Web Push

    H->>C: collecter(depuis = dernière collecte)
    C->>S: recuperer(depuis) pour chaque source
    S-->>C: textes (XML, JSON)
    C->>DB: INSERT document (empreinte SHA-256 unique)
    C->>C: filtre de périmètre puis extraction
    C->>DB: INSERT changement (CII, taux, 30 % vers 20 %)

    H->>M: traiter les nouveaux changements
    M->>DB: SELECT documents filtrés et changements non traités
    M->>M: assembler_tous : chaque changement avec son document, dans l'ordre de la procédure
    loop pour chaque changement
        M->>M: rattacher (A2), statut (A3), dater (A4)
        M->>M: résumer (S3), voir séquence 2
        M->>DB: INSERT ou UPDATE mesure, version_mesure, transition_mesure, resume
    end
    M->>DB: relancer_resumes_en_attente()
    M->>DB: appliquer_entrees_en_vigueur(aujourd'hui)

    H->>K: cibler et chiffrer
    K->>DB: mesures_modifiees_depuis(dernier passage), clients du dispositif
    K->>K: simulation loi actuelle puis réforme (OpenFisca)
    K->>DB: INSERT impact (client B, écart 40 000 €), calcul

    H->>A: alerter
    A->>DB: SELECT impacts nouveaux ou modifiés
    A->>DB: INSERT ou UPDATE alerte (une par mesure et par client)
    alt montant au-dessus du seuil du consultant
        A->>WP: notification urgente
    else sous le seuil
        A->>DB: l'alerte attend la liste de la semaine
    end
```

Une erreur dans un lot n'arrête pas les suivants : chaque lot traite ce qui est prêt, et reprend le reste à la nuit suivante.

## 2 · Résumer un changement (S3, lot 2)

Ce qui se passe dans `ResumeurS3.resumer()` quand un fournisseur LLM est configuré. Sans fournisseur, le rédacteur par gabarit remplace les appels au LLM. Si le LLM échoue encore après sa nouvelle tentative (`ErreurLLM`), le gabarit fournit un texte provisoire et le résumé est enregistré **en attente** ; `relancer_resumes_en_attente()` le refait à la tâche suivante.

```mermaid
sequenceDiagram
    autonumber
    participant SM as SuiviMesures
    participant DB as Table resume
    participant R as ResumeurS3
    participant CX as SourceContexte
    participant RL as RedacteurLLM
    participant SL as ServiceLLM
    participant CA as Cache appel_llm
    participant F as Fournisseur LLM
    participant AM as anti_montant

    SM->>DB: résumé existant pour (empreinte texte, empreinte changement, version) ?
    alt déjà résumé
        DB-->>SM: résumé en cache
    else jamais résumé
        SM->>R: resumer(changement, date_vigueur)
        R->>CX: texte_article(article visé), doctrine(dispositif)
        CX-->>R: contexte (article du CGI, BOFiP)
        R->>R: drapeaux (décret à paraître, extraction à revoir, termes non définis)

        Note over R,F: Premier appel : la citation
        R->>RL: citer(changement, contexte)
        RL->>SL: generer("s3_citation", CitationLLM, valeurs)
        SL->>CA: lire(clé de la requête)
        alt réponse en cache
            CA-->>SL: réponse
        else
            SL->>F: completer(requête)
            F-->>SL: JSON
            SL->>SL: validation Pydantic, une nouvelle tentative si invalide
            SL->>CA: ecrire(clé, réponse valide)
        end
        SL-->>RL: citation
        RL-->>R: citation
        R->>R: citation présente mot pour mot dans le texte ?
        opt citation introuvable
            R->>R: reprendre le passage cité par le lot 1 (drapeau si lui aussi introuvable)
        end

        Note over R,F: Second appel : le résumé
        R->>RL: rediger(changement, citation, contexte, date)
        RL->>SL: generer("s3_resume", ResumeLLM, valeurs)
        SL-->>RL: résumé de 3 à 5 phrases
        RL-->>R: résumé
        R->>AM: montants_non_justifies(résumé, citation)
        alt montant inventé
            R->>RL: rediger(..., regeneration = vrai)
            RL-->>R: nouveau résumé
            R->>AM: montants_non_justifies(...)
            opt toujours un montant inventé
                R->>R: résumé par gabarit
            end
        end
        R-->>SM: ResumeProduit (texte, citation, méthode, motifs)
        SM->>DB: INSERT resume
    end
```

## 3 · Le consultant décide d'une action (G5, G6)

Le lundi, le consultant ouvre la liste de la semaine et traite la ligne du client B.

```mermaid
sequenceDiagram
    autonumber
    actor U as Consultant
    participant W as PWA React
    participant API as FastAPI
    participant DB as PostgreSQL

    U->>W: ouvre Leypilot
    W->>API: GET /liste-semaine (jeton JWT)
    API->>API: vérifie le jeton, rôle consultant
    API->>DB: SET leypilot.utilisateur_id puis SELECT ligne_liste
    Note right of DB: Row-Level Security : seules ses lignes reviennent
    DB-->>API: « Client B, 40 000 € en jeu, six semaines, rendez-vous cette semaine »
    API-->>W: liste triée par score
    U->>W: ouvre l'action du client B
    W->>API: GET /actions/{id}
    API->>DB: action, résumé, citation, statut, trace du calcul
    API-->>W: détail
    U->>W: Accepter + motif « RDV fixé jeudi »
    W->>API: POST /actions/{id}/decision
    alt motif vide
        API-->>W: 422, motif obligatoire
    else motif présent
        API->>DB: BEGIN
        API->>DB: UPDATE action SET statut = acceptee
        API->>DB: INSERT journal_decision (qui, quoi, quand, pourquoi, commit des règles)
        API->>DB: COMMIT
        API-->>W: 200
        W-->>U: action acceptée
    end
```

Leypilot ne contacte jamais le client : aucune route de l'API n'envoie de message vers l'extérieur.

## 4 · L'expert valide une règle (M3, M4, M5)

Déclencheur : la loi qui baisse le CII est publiée au JO, la mesure passe à « publiée ».

```mermaid
sequenceDiagram
    autonumber
    participant H as Planificateur
    participant K as Calcul P3
    participant SL as ServiceLLM
    participant DB as PostgreSQL
    actor E as Expert
    participant API as FastAPI
    participant G as Dépôt Git des règles

    H->>K: proposer les règles des mesures publiées
    K->>DB: mesures_publiees_depuis(hier)
    K->>SL: generer("m3_brouillon", BrouillonRegle, changement)
    SL-->>K: cii.taux = 0,20 au 01/01/2026 + citation
    K->>DB: INSERT regle_proposee (statut en_attente)
    Note over DB: Les impacts restent « chiffrage en attente de validation »

    E->>API: GET /regles?statut=en_attente
    API-->>E: brouillon, ancienne valeur, citation, lien Légifrance
    alt valide ou corrige
        E->>API: POST /regles/{id}/valider
        API->>K: valider(regle, expert)
        K->>G: écrit parameters/cii/taux.yaml puis commit
        G-->>K: identifiant du commit
        K->>DB: UPDATE regle_proposee SET statut = validee, commit_git
        Note over K,DB: À la tâche suivante, les impacts sont recalculés avec ce commit
    else rejette
        E->>API: POST /regles/{id}/rejeter + motif
        API->>K: rejeter(regle, expert, motif)
        K->>DB: UPDATE regle_proposee SET statut = rejetee
    end
```
