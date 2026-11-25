import { Bell, ChevronDown, Menu, Search } from "lucide-react";
import { useLocation } from "react-router-dom";

const routeTitles = {
  "/dashboard": "Tableau de bord",
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

function Header({ onMenuClick, search, searchRef, onSearchChange, onNotificationsClick }) {
  const { pathname } = useLocation();

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="menu-toggle" onClick={onMenuClick} aria-label="Ouvrir le menu">
          <Menu size={20} />
        </button>
        <div className="breadcrumbs">
          <span className="breadcrumb-home">Leypilot</span>
          <span className="breadcrumb-slash">/</span>
          <strong>{routeTitles[pathname] || "Espace consultant"}</strong>
        </div>
      </div>
      <div className="topbar-tools">
        <label className="global-search">
          <Search size={16} />
          <input
            ref={searchRef}
            type="search"
            aria-label="Rechercher dans le tableau de bord"
            placeholder="Rechercher un client, un texte..."
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
          <kbd>⌘ K</kbd>
        </label>
        <button className="header-icon-button notification-button" onClick={onNotificationsClick} aria-label="Voir les alertes, 4 non lues">
          <Bell size={18} />
          <span className="notification-dot" />
        </button>
        <span className="header-divider" />
        <div className="profile-menu" aria-label="Consultante connectée : Marie-Reine">
          <span className="profile-avatar">MR</span>
          <span className="profile-copy"><strong>Marie-Reine</strong><small>Consultante</small></span>
          <ChevronDown size={15} />
        </div>
      </div>
    </header>
  );
}

export default Header;
