# 9 · Architecture : composants et déploiement

## 1 · Diagramme de composants

Chaque composant expose une interface (○) et n'en connaît pas l'implémentation. La couche LLM sert surtout le lot 2 (S3, A4) ; les autres lots l'appellent en secours (S2) ou pour M3 et G4. Les lots communiquent **par la base** (une table, un propriétaire) et par quelques fonctions de lecture publiées.

```mermaid
flowchart LR
    subgraph client["Navigateur"]
        pwa["«composant»<br/>PWA React"]
        sw["«composant»<br/>Service worker<br/>(Web Push)"]
    end

    subgraph serveur["Serveur Leypilot"]
        api["«composant»<br/>API FastAPI<br/>JWT, rôles"]
        taches["«composant»<br/>Planificateur<br/>APScheduler"]

        subgraph lots["Modules métier"]
            collecte["«composant» Collecte P1<br/>○ Connecteur.recuperer(depuis)"]
            mesure["«composant» Mesure P2<br/>○ assembler_tous(documents, changements)<br/>○ SuiviMesures.traiter()<br/>○ mesures_modifiees_depuis()<br/>○ mesures_publiees_depuis()"]
            calcul["«composant» Calcul P3<br/>○ chiffrer(mesure)<br/>○ valider(regle)"]
            alertes["«composant» Alertes P4<br/>○ alerter()<br/>○ produire_liste()"]
        end

        llm["«composant» Couche LLM P2<br/>○ ServiceLLM.generer()"]
        moteur["«composant»<br/>OpenFisca + paquet leypilot"]
        db[("PostgreSQL")]
    end

    sources["Légifrance PISTE<br/>Assemblée, Sénat<br/>BOFiP"]
    fournisseur["API du LLM"]
    push["Service push<br/>du navigateur"]
    git["Dépôt Git<br/>des règles"]

    pwa -- "HTTPS JSON" --> api
    api -- "appelle" --> lots
    taches -- "lance chaque nuit" --> lots
    lots -- "SQLAlchemy" --> db
    api -- "lit (RLS)" --> db
    lots -- "via ServiceLLM" --> llm
    llm -- "HTTPS, textes publics seulement" --> fournisseur
    collecte -- "HTTPS" --> sources
    calcul --> moteur
    calcul --> git
    alertes -- "pywebpush" --> push
    push --> sw
```

## 2 · Contrats entre lots

| De → vers | Ce qui passe | Forme | Déclencheur |
|---|---|---|---|
| P1 → P2 | Documents filtrés (texte, type, date, identifiants officiels) et changements détectés (dispositif, paramètre, ancienne et nouvelle valeur, passage cité) | Tables `document`, `changement` ; objets `DocumentFiltre`, `ChangementDetecte` (Pydantic, `leypilot/mesure/entree.py`) | Fin de la détection, chaque nuit |
| P2 → P3 | Mesures : dispositif, paramètre et valeurs, conditions, statut, niveau, date d'entrée en vigueur, résumé, documents | Tables `mesure`, `version_mesure`, `resume` ; fonctions `mesures_modifiees_depuis`, `mesures_publiees_depuis`, `vue_mesure` | Fin du suivi |
| P3 → P4 | Impacts chiffrés, trace, piste | Tables `impact`, `calcul` | Fin du chiffrage |
| P4 → P5 | Alertes, actions, liste de la semaine | Tables `alerte`, `action`, `liste_semaine` | Fin des alertes, dimanche soir |
| P2 → tous | Appel au LLM | `ServiceLLM.generer(nom_prompt, Schema, valeurs)` | À la demande |
| P5 → tous | Base, configuration, planificateur, API | `leypilot.commun`, `leypilot.taches` | — |

Le contrat P1 → P2 (`leypilot/mesure/entree.py`) est provisoire : il reste à valider avec la personne 1. Les données descendent en cascade : la personne 4 ne lit pas les mesures, elle reçoit niveau, date et résumé avec les impacts de la personne 3.

## 3 · Diagramme de déploiement

Tout tient sur une seule machine virtuelle, sans GPU. Le seul service externe qui reçoit des données est l'API du LLM, et il ne reçoit que des textes officiels publics.

```mermaid
flowchart TB
    subgraph poste["«device» Poste du consultant ou de l'expert"]
        nav["«execution environment» Navigateur<br/>PWA React + service worker"]
    end

    subgraph vm["«device» Machine virtuelle · 2 vCPU, 4 Go RAM"]
        subgraph docker["«execution environment» Docker Compose"]
            c_api["«container» api<br/>uvicorn + FastAPI<br/>+ modules leypilot<br/>+ OpenFisca"]
            c_taches["«container» taches<br/>APScheduler<br/>même image que api"]
            c_db["«container» postgres<br/>PostgreSQL 16"]
        end
        disque[("«artifact»<br/>Fichiers bruts des textes<br/>volume Docker")]
        regles[("«artifact»<br/>Dépôt Git des règles YAML")]
    end

    subgraph externes["Services externes"]
        piste["«device» API Légifrance PISTE"]
        opendata["«device» Open data AN, Sénat, BOFiP"]
        llm_ext["«device» API du LLM"]
        push_ext["«device» Service push<br/>(Google, Mozilla, Apple)"]
    end

    nav -- "HTTPS 443" --> c_api
    c_api -- "TCP 5432" --> c_db
    c_taches -- "TCP 5432" --> c_db
    c_taches --> disque
    c_taches --> regles
    c_api --> regles
    c_taches -- "HTTPS, OAuth2" --> piste
    c_taches -- "HTTPS" --> opendata
    c_taches -- "HTTPS" --> llm_ext
    c_taches -- "HTTPS, VAPID" --> push_ext
    push_ext -- "notification" --> nav
```

## 4 · Tâches planifiées

Horaires proposés, à fixer par la personne 5 avec chaque lot.

| Tâche | Quand | Lot | Fait quoi |
|---|---|---|---|
| Collecte | Chaque nuit, 2 h ; toutes les 4 à 6 h d'octobre à décembre (PLF) | P1 | S1, A1 : textes nouveaux depuis le dernier passage |
| Contrôle de complétude | Chaque matin, 6 h | P1 | Compare au sommaire du JO, alerte technique si écart |
| Détection | Après la collecte | P1 | S2 : changements |
| Suivi des mesures | Après la détection | P2 | A2 à A5, S3 |
| Entrées en vigueur | Chaque jour, 0 h 30 | P2 | `appliquer_entrees_en_vigueur(aujourd'hui)` |
| Ciblage et chiffrage | Après le suivi | P3 | S4, M2, G3 ; M3 pour les mesures publiées |
| Alertes | Après le chiffrage | P4 | S5 : création, mise à jour, Web Push urgent |
| Relances | Toutes les heures | P4 | Alertes urgentes non lues après le délai |
| Liste de la semaine | Dimanche, 20 h | P4 | G1, G2, G4 |

Les tâches de la nuit s'enchaînent dans l'ordre de la cascade ; chacune ne traite que ce que la précédente a produit.

## 5 · Sécurité

| Exigence | Mise en œuvre |
|---|---|
| Un consultant ne voit que son portefeuille | JWT → `SET leypilot.utilisateur_id` → Row-Level Security sur les tables client, impact, alerte, action |
| L'expert ne voit pas les données client | Rôle `expert` : routes des règles et des rattachements seulement |
| Aucune donnée client vers le LLM | Les prompts ne reçoivent que des textes officiels et des champs de `Changement` ; les phrases G4 utilisent des emplacements remplis après coup par le moteur |
| Secrets hors du dépôt | `.env` (clé LLM, identifiants PISTE, secret JWT, clés VAPID), jamais commité |
| Journal non modifiable | Droits retirés + trigger sur `journal_decision` |
