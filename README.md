# Leypilot

Copilote de veille réglementaire pour les consultants. Leypilot surveille les textes officiels (Journal officiel, Parlement, BOFiP), repère les changements qui touchent le CIR, le CII et la JEI, chiffre leur effet pour chaque client et prévient le bon consultant au bon moment, avec une proposition d'action à mener.

## Ce que fait l'outil

1. **Collecter et détecter** : récupérer chaque nuit les nouveaux textes et en extraire les changements (taux, plafonds, conditions).
2. **Comprendre et suivre** : résumer chaque changement en citant le texte, puis suivre la mesure de son dépôt à son entrée en vigueur.
3. **Chiffrer** : calculer en euros l'écart pour chaque client, « loi actuelle contre réforme », avec un moteur déterministe (OpenFisca).
4. **Cibler, alerter, prioriser** : prévenir les consultants concernés, classer les actions par priorité et envoyer la liste de la semaine.
5. **Décider et tracer** : le consultant accepte, reporte ou rejette l'action ; chaque décision est inscrite dans un journal non modifiable.

## Principes

- **Le LLM ne produit jamais un montant.** Tous les montants viennent du moteur de calcul.
- **Pas de GPU.** Le LLM est appelé par API (Mistral, Claude en secours).
- **Pas d'e-mail.** Les alertes passent par l'application (notifications Web Push).
- **Sources officielles d'abord.** Chaque résumé cite le passage du texte dont il vient.

## Architecture

| Lot | Responsable | Dossier | Fonctions |
|---|---|---|---|
| Collecter et détecter | Personne 1 | `leypilot/collecte/` | S1, S2, A1 |
| Comprendre et suivre la mesure | Personne 2 | `leypilot/mesure/`, `leypilot/commun/llm/` | S3, A2 à A5, couche LLM |
| Chiffrer | Personne 3 | `leypilot/calcul/`, `openfisca_leypilot/` | M1 à M6, G3 |
| Cibler, alerter, prioriser | Personne 4 | `leypilot/alertes/` | S4, S5, G1, G2, G4 |
| Plateforme et interface | Personne 5 | `leypilot/commun/`, `leypilot/api/`, `leypilot/taches/`, `web/`, `migrations/` | Socle, G5, G6 |

Les modules communiquent par la base PostgreSQL : chaque table a un seul propriétaire qui l'écrit, les autres la lisent.

**Technologies :** Python 3.12, FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pydantic, OpenFisca, rapidfuzz, Jinja2, APScheduler, React (PWA).

## Structure du dépôt

```
leypilot/
├── README.md                 ce fichier
├── CONTRIBUTING.md           conventions, branches, revue de code
├── docker-compose.yml        PostgreSQL + API
├── Dockerfile                image de l'API
├── pyproject.toml            dépendances, ruff, pytest
├── .env.example              clés à renseigner (le .env reste hors de Git)
├── .github/workflows/ci.yml  ruff + pytest à chaque pull request
├── docs/
│   ├── conception/           MCD, MLD, diagrammes UML
│   └── adr/                  une décision d'architecture par fichier
├── leypilot/
│   ├── commun/               config, connexion à la base, schémas Pydantic   P5
│   │   ├── modeles/          tables SQLAlchemy, un fichier par lot          chaque lot
│   │   └── llm/              couche LLM partagée                            P2
│   ├── collecte/             S1, S2, A1                                     P1
│   ├── mesure/               S3, A2 à A5                                    P2
│   ├── calcul/               M1 à M6, G3                                    P3
│   ├── alertes/              S4, S5, G1, G2, G4                             P4
│   ├── api/                  FastAPI, JWT, G5, G6                           P5
│   └── taches/               planification des tâches de nuit               P5
├── openfisca_leypilot/       paramètres YAML, formules, cas tests           P3
├── web/                      interface React en PWA                         P5
├── migrations/               migrations Alembic                             P5
├── donnees_exemple/          jeux de données, dont le client B              chaque lot
└── tests/
    ├── unitaires/            un dossier par lot                             chaque lot
    └── fil_rouge/            scénario client B de bout en bout              toute l'équipe
```

## Démarrage

Prérequis : Git, Docker et Docker Compose. Python 3.12 si vous lancez le code sans Docker.

```bash
git clone https://github.com/papy-studio/Leypillot-.git leypilot
cd leypilot
cp .env.example .env          # puis renseigner les clés
docker compose up --build
```

L'API répond sur http://localhost:8000 (santé : `/sante`, documentation : `/docs`).

Sans Docker, pour développer et lancer les tests :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

## Fil rouge : le client B

Un même cas traverse les cinq lots et sert de test de bout en bout du MVP : le taux du CII passe de 30 % à 20 %, le client B a 400 000 € de dépenses éligibles, soit **40 000 € en jeu**, à six semaines de l'échéance. Le scénario se trouve dans `tests/fil_rouge/`.

## Contribuer

Lire [CONTRIBUTING.md](CONTRIBUTING.md) avant la première pull request. En bref : une branche par tâche, chacun ne modifie que ses dossiers, et toute modification de `leypilot/commun/` ou `migrations/` est relue par la personne 5.
