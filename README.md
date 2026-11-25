# LEYPILOT

Interface frontend de veille réglementaire pour les consultants Leyton. Le dépôt ne contient pas de backend ; les exemples du tableau de bord sont des données de démonstration isolées des composants.

## Démarrage local

```powershell
Set-Location .\frontend
npm install
npm run dev
```

## Architecture frontend

- `frontend/src/components/` : layout partagé, navigation et écrans.
- `frontend/src/data/` : fixtures de démonstration, indépendantes de l’interface.
- `frontend/src/services/` : point d’accès aux données, remplaçable par un adaptateur HTTP lorsque les contrats FastAPI seront définis.
- React Router gère la navigation ; les sections non développées disposent de pages provisoires.
- Recharts affiche l’évolution des changements réglementaires.

Le tableau de bord et le layout responsive sont la première étape. Les autres écrans seront développés séparément. Les données affichées sont fictives et ne constituent pas une analyse juridique ou fiscale.
