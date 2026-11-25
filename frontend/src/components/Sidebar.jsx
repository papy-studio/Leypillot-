import {
  Activity,
  Bell,
  BookOpen,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  CircleUserRound,
  ClipboardCheck,
  Clock3,
  Gauge,
  Settings2,
  Sparkles,
  Target,
  WalletCards,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const navigationGroups = [
  {
    label: "Accueil",
    items: [{ label: "Tableau de bord", path: "/dashboard", icon: Gauge }],
  },
  {
    label: "01 — Anticiper",
    items: [
      { label: "Veille réglementaire", path: "/veille", icon: BookOpen },
      { label: "Réformes anticipées", path: "/reformes", icon: Sparkles },
    ],
  },
  {
    label: "02 — Mesurer",
    items: [
      { label: "Portefeuille clients", path: "/clients", icon: BriefcaseBusiness },
      { label: "Simulations financières", path: "/simulations", icon: WalletCards },
      { label: "Analyse des impacts", path: "/impacts", icon: ChartNoAxesCombined },
    ],
  },
  {
    label: "03 — Agir",
    items: [
      { label: "Mes alertes", path: "/alertes", icon: Bell, badge: "4" },
      { label: "Actions recommandées", path: "/actions", icon: Target },
      { label: "Plan d’action", path: "/plan-action", icon: ClipboardCheck },
    ],
  },
  {
    label: "Configuration",
    items: [
      { label: "Paramètres et seuils", path: "/parametres", icon: Settings2 },
      { label: "Historique des décisions", path: "/historique", icon: Clock3 },
      { label: "Mon profil", path: "/profil", icon: CircleUserRound },
    ],
  },
];

function Sidebar({ mobileOpen, onNavigate }) {
  return (
    <>
      <button
        className={`sidebar-backdrop ${mobileOpen ? "is-visible" : ""}`}
        aria-label="Fermer le menu"
        onClick={onNavigate}
        tabIndex={mobileOpen ? 0 : -1}
      />
      <aside className={`sidebar ${mobileOpen ? "is-open" : ""}`}>
        <NavLink className="brand" to="/dashboard" onClick={onNavigate} aria-label="Leypilot, accueil">
          <span className="brand-mark"><Activity size={19} strokeWidth={2.5} /></span>
          <span className="brand-name">LEY<span>PILOT</span></span>
        </NavLink>

        <div className="workspace-switcher">
          <div className="workspace-avatar">L</div>
          <div className="workspace-copy">
            <span>ESPACE CONSULTANT</span>
            <strong>Leyton Conseil</strong>
          </div>
          <span className="workspace-dot" aria-label="Espace actif" />
        </div>

        <nav className="side-nav" aria-label="Navigation principale">
          {navigationGroups.map((group) => (
            <section className="nav-group" key={group.label}>
              <h2>{group.label}</h2>
              {group.items.map(({ label, path, icon: Icon, badge }) => (
                <NavLink
                  className={({ isActive }) => `side-link${isActive ? " is-active" : ""}`}
                  key={path}
                  to={path}
                  onClick={onNavigate}
                >
                  <Icon size={17} strokeWidth={1.8} />
                  <span>{label}</span>
                  {badge && <span className="nav-badge">{badge}</span>}
                </NavLink>
              ))}
            </section>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-help">
            <span className="help-icon"><Sparkles size={16} /></span>
            <div>
              <strong>Un œil sur demain</strong>
              <span>Votre veille, en continu.</span>
            </div>
          </div>
          <div className="sidebar-version">LEYPILOT <span>·</span> ESPACE CONSULTANT</div>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
