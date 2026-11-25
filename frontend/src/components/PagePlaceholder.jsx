import { ArrowLeft, Construction } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

const titles = {
  "/veille": "Veille réglementaire",
  "/reformes": "Réformes anticipées",
  "/clients": "Portefeuille clients",
  "/simulations": "Simulations financières",
  "/impacts": "Analyse des impacts",
  "/alertes": "Mes alertes",
  "/actions": "Actions recommandées",
  "/plan-action": "Plan d’action",
  "/parametres": "Paramètres et seuils",
  "/historique": "Historique des décisions",
  "/profil": "Mon profil",
};

function PagePlaceholder() {
  const { pathname } = useLocation();
  const title = Object.entries(titles).find(([path]) =>
    pathname === path || pathname.startsWith(`${path}/`),
  )?.[1] || "Page introuvable";

  return (
    <section className="placeholder-page">
      <div className="placeholder-icon"><Construction size={23} /></div>
      <span className="eyebrow">ESPACE CONSULTANT</span>
      <h1>{title}</h1>
      <p>Cette section sera développée dans une prochaine étape.</p>
      <Link to="/dashboard"><ArrowLeft size={15} /> Retour au tableau de bord</Link>
    </section>
  );
}

export default PagePlaceholder;
