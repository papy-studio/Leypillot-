# 8 · Diagrammes d'activités

Les algorithmes qui portent des règles métier, décrits pas à pas. Losange = décision, rectangle arrondi = début ou fin.

## 1 · Rattacher un changement à une mesure (A2, lot 2)

Conforme à `leypilot/mesure/rattachement.py` et `suivi.py`.

```mermaid
flowchart TD
    debut(["Nouveau changement"]) --> filtre["Garder les mesures compatibles :<br/>même dispositif, statut non final,<br/>même dossier législatif s'il est connu,<br/>même article (244 quater B ≠ 44 sexies-0 A)"]
    filtre --> amd{"Le n° d'amendement<br/>est-il déjà connu<br/>d'une mesure ?"}
    amd -- oui --> auto_amd["Rattacher<br/>méthode : amendement, score 100"]
    amd -- non --> score["Calculer pour chaque candidate :<br/>0,5 × ressemblance de l'article<br/>+ 0,5 × ressemblance du paramètre<br/>(rapidfuzz token_set_ratio)"]
    score --> seuil_bas{"Meilleur score<br/>≥ 70 ?"}
    seuil_bas -- non --> nouvelle["Créer une nouvelle mesure"]
    seuil_bas -- oui --> seuil_haut{"Score ≥ 90, ou<br/>identifiant officiel commun<br/>(dossier, NOR, ELI) ?"}
    seuil_haut -- oui --> auto_sim["Rattacher<br/>méthode : similarité"]
    seuil_haut -- non --> attente["Mettre en attente<br/>rattachement_a_valider"]
    attente --> humain{"L'humain<br/>confirme ?"}
    humain -- oui --> auto_hum["Rattacher<br/>méthode : humain"]
    humain -- non --> nouvelle
    auto_amd --> suite
    auto_sim --> suite
    auto_hum --> suite
    nouvelle --> suite(["Appliquer le statut (A3), dater (A4), résumer (S3)"])
```

**Fil rouge** : l'adoption du client B arrive avec un article écrit autrement (« CGI, art. 244 quater B, II, k » au lieu de « article 244 quater B du code général des impôts ») et sans numéro d'amendement. Le dossier législatif PLF2026 est commun : le changement est rattaché automatiquement à la même mesure (`donnees_exemple/lot2_client_b.json`).

## 2 · Dater l'entrée en vigueur (A4, lot 2)

```mermaid
flowchart TD
    debut(["Changement à dater"]) --> regex{"Une clause connue<br/>dans le passage cité<br/>ou le texte ?"}
    regex -- oui --> type{"Date écrite<br/>dans la clause ?"}
    type -- "oui : « à compter du 1er janvier 2026 »" --> certaine["Date certaine"]
    type -- "non : « exercices ouverts à compter<br/>de la publication »" --> estimee_rel["Date estimée,<br/>déduite de la publication"]
    regex -- non --> llm{"LLM<br/>configuré ?"}
    llm -- oui --> appel["Prompt a4_date<br/>réponse JSON validée"]
    appel --> trouve{"Date<br/>trouvée ?"}
    trouve -- oui --> estimee_llm["Date estimée<br/>méthode : LLM"]
    trouve -- non --> pub
    llm -- non --> pub{"Date de publication<br/>connue ?"}
    pub -- oui --> droit["Lendemain de la publication<br/>(droit commun), date estimée"]
    pub -- non --> rien["Pas de date"]
    certaine --> ecrire
    estimee_rel --> ecrire
    estimee_llm --> ecrire
    droit --> ecrire
    ecrire{"La mesure a déjà<br/>une date certaine et<br/>la nouvelle est estimée ?"}
    ecrire -- oui --> garder(["Garder l'ancienne date"])
    ecrire -- non --> maj(["Enregistrer la date<br/>et calculer le compte à rebours"])
    rien --> fin(["Mesure sans date"])
```

## 3 · Résumer avec citation vérifiée (S3, lot 2)

```mermaid
flowchart TD
    debut(["Changement rattaché"]) --> cache{"Résumé déjà fait<br/>pour ce texte, ce changement<br/>et cette version ?"}
    cache -- oui --> fin_cache(["Réutiliser le résumé"])
    cache -- non --> ctx["Retrouver le contexte par identifiant :<br/>article du CGI, doctrine BOFiP"]
    ctx --> drap["Poser les drapeaux de doute :<br/>décret à paraître, extraction à revoir,<br/>termes non définis"]
    drap --> citer["Demander la citation"]
    citer --> mot{"Citation présente<br/>mot pour mot ?"}
    mot -- oui --> rediger
    mot -- non --> s2["Prendre le passage cité par S2"]
    s2 --> mot2{"Présent<br/>mot pour mot ?"}
    mot2 -- non --> drap_cit["Drapeau : citation non vérifiée"]
    mot2 -- oui --> rediger
    drap_cit --> rediger["Rédiger 3 à 5 phrases :<br/>ce qui change, pour quel dispositif,<br/>à partir de quand"]
    citer -. "LLM en échec après<br/>la nouvelle tentative" .-> attente(["Texte provisoire du gabarit,<br/>résumé en attente, relancé<br/>à la tâche suivante"])
    rediger --> montant{"Montant absent<br/>de la citation ?"}
    montant -- non --> ok
    montant -- oui --> regen["Régénérer une fois"]
    regen --> montant2{"Toujours un<br/>montant inventé ?"}
    montant2 -- non --> ok
    montant2 -- oui --> gabarit["Rédiger par gabarit"]
    gabarit --> ok(["Enregistrer le résumé<br/>avec citation et drapeaux"])
```

## 4 · Produire la liste de la semaine (G1, G2, G4, lot 4)

Proposition à valider par la personne 4.

```mermaid
flowchart TD
    debut(["Dimanche soir"]) --> chaque["Pour chaque consultant"]
    chaque --> actions["Lire ses actions proposées<br/>et ses actions reportées arrivées à échéance"]
    actions --> score["Calculer le score :<br/>montant normalisé × facteur d'urgence<br/>(poids du consultant)"]
    score --> tri["Trier par score décroissant"]
    tri --> ligne["Rédiger chaque ligne par gabarit Jinja2<br/>avec les montants du moteur"]
    ligne --> phrase{"Phrase d'action<br/>déjà rédigée ?"}
    phrase -- non --> llm["LLM : phrase avec emplacements<br/>{montant}, {delai}"]
    llm --> chiffre{"Chiffre en dur<br/>dans la phrase ?"}
    chiffre -- oui --> modele["Phrase par défaut<br/>de l'action type"]
    chiffre -- non --> remplir
    modele --> remplir["Le moteur remplit les emplacements"]
    phrase -- oui --> enreg
    remplir --> enreg["Enregistrer liste_semaine<br/>et ligne_liste"]
    enreg --> autre{"Autre<br/>consultant ?"}
    autre -- oui --> chaque
    autre -- non --> fin(["Liste affichée le lundi en page d'accueil"])
```
