# 7 · Diagrammes d'états

Chaque objet qui a un cycle de vie a son diagramme. Une transition s'écrit `événement [condition] / effet`.

## 1 · Mesure (A3, lot 2) · conforme à `leypilot/mesure/etats.py`

```mermaid
stateDiagram-v2
    direction LR
    state "Proposée" as proposee
    state "Votée" as votee
    state "Publiée" as publiee
    state "Appliquée" as appliquee
    state "Abandonnée" as abandonnee

    [*] --> proposee : dépôt
    [*] --> votee : adoption
    [*] --> publiee : publication (décret, arrêté)

    proposee --> votee : adoption
    proposee --> abandonnee : rejet ou suppression
    votee --> publiee : publication au JO / date_publication
    votee --> abandonnee : censure du Conseil constitutionnel
    publiee --> appliquee : [date d'entrée en vigueur atteinte]

    appliquee --> [*]
    abandonnee --> [*]

    note right of proposee
        Niveau « information » :
        on prévient, aucune action (A5)
    end note
    note right of votee
        Niveau « action » à partir d'ici
    end note
```

| Règle | Comportement codé |
|---|---|
| Un événement qui confirme le statut actuel (deuxième amendement d'une mesure proposée) | Aucune transition ; la mesure est complétée (identifiants, résumé) |
| Une transition absente de la table (publication d'une mesure seulement proposée) | `TransitionInterdite` : le statut ne bouge pas, la mesure passe « à revoir » |
| Un rejet sur une mesure inconnue | Ignoré, signalé dans les erreurs du traitement |
| Passage en « appliquée » | Pas d'événement de la source : la tâche quotidienne `appliquer_entrees_en_vigueur` compare la date |
| Chaque transition | Une ligne dans `transition_mesure` (de, vers, événement, date) |

**Points ouverts** : statut « En attente de décret » entre Publiée et Appliquée, et cycle propre au BOFiP (consultation, publication). Ils s'ajoutent à la table `TRANSITIONS` sans toucher au reste.

## 2 · Rattachement à valider (A2, lot 2)

```mermaid
stateDiagram-v2
    direction LR
    state "En attente" as attente
    state "Confirmé" as confirme
    state "Refusé" as refuse

    [*] --> attente : score entre 70 et 90
    attente --> confirme : l'humain confirme / changement rattaché, transition appliquée
    attente --> refuse : l'humain refuse / nouvelle mesure créée
    confirme --> [*]
    refuse --> [*]
```

Une décision déjà prise ne peut plus être reprise (`RattachementIntrouvable`).

## 3 · Résumé (S3, lot 2)

Un résumé n'est jamais réécrit : on en crée un nouveau quand le changement, le texte ou la version du rédacteur change, ou quand un résumé en attente est relancé avec succès (le provisoire perd alors son drapeau « en attente »).

```mermaid
stateDiagram-v2
    direction LR
    state "Rédaction LLM" as llm
    state "Régénération" as regen
    state "Gabarit" as gabarit
    state "En attente" as attente
    state "Enregistré" as enregistre
    state verif <<choice>>
    state verif2 <<choice>>

    [*] --> llm : fournisseur configuré
    [*] --> gabarit : pas de fournisseur
    llm --> attente : ErreurLLM après la nouvelle tentative / texte provisoire du gabarit
    attente --> llm : relance à la tâche suivante
    llm --> verif : texte produit
    verif --> enregistre : aucun montant hors citation
    verif --> regen : montant hors citation
    regen --> verif2
    verif2 --> enregistre : corrigé
    verif2 --> gabarit : toujours un montant
    gabarit --> enregistre
    enregistre --> [*]
```

## 4 · Règle proposée (M3, M4, lot 3)

```mermaid
stateDiagram-v2
    direction LR
    state "En attente" as attente
    state "Validée" as validee
    state "Corrigée" as corrigee
    state "Rejetée" as rejetee

    [*] --> attente : loi publiée au JO / brouillon LLM + citation
    attente --> validee : l'expert valide / YAML commité
    attente --> corrigee : l'expert corrige / YAML corrigé commité
    attente --> rejetee : l'expert rejette avec motif
    validee --> [*]
    corrigee --> [*]
    rejetee --> [*]

    note right of attente
        Les impacts affichent
        « chiffrage en attente de validation »
    end note
```

## 5 · Alerte (S5, lot 4)

Une seule alerte par mesure et par client, mise à jour à chaque étape de la mesure.

```mermaid
stateDiagram-v2
    state "Non lue" as non_lue
    state "Relancée" as relancee
    state "Lue" as lue
    state "Avis donné" as avis

    [*] --> non_lue : impact nouveau / Web Push si urgente
    non_lue --> relancee : [urgente et délai de relance dépassé] / Web Push
    non_lue --> lue : clic « Lu »
    relancee --> lue : clic « Lu »
    lue --> avis : « Utile » ou « Pas utile »
    lue --> non_lue : la mesure change d'étape / alerte mise à jour
    avis --> non_lue : la mesure change d'étape / alerte mise à jour
```

Une alerte n'est jamais supprimée : le seuil change l'urgence, pas la visibilité.

## 6 · Action (G1 à G5, lots 4 et 5)

```mermaid
stateDiagram-v2
    direction LR
    state "Proposée" as proposee
    state "Acceptée" as acceptee
    state "Reportée" as reportee
    state "Rejetée" as rejetee

    [*] --> proposee : [mesure au moins votée] / score calculé
    proposee --> acceptee : accepter(motif) / journal
    proposee --> reportee : reporter(date, motif) / journal
    proposee --> rejetee : rejeter(motif) / journal
    reportee --> proposee : [date de report atteinte]
    acceptee --> [*]
    rejetee --> [*]
```

La garde `[mesure au moins votée]` est garantie par le trigger A5 : la base refuse l'insertion sinon. Chaque transition déclenchée par le consultant ajoute une ligne dans `journal_decision`.
