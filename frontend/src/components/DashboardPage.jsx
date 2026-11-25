import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  FileText,
  Info,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  UsersRound,
} from "lucide-react";
import { Link, useOutletContext } from "react-router-dom";
import { getDashboardData } from "../services/dashboardService";

const RegulatoryTrendChart = lazy(() => import("./RegulatoryTrendChart"));

const moneyFormat = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});
const numberFormat = new Intl.NumberFormat("fr-FR");

const metricIcons = {
  texts: FileText,
  changes: TrendingUp,
  reforms: Sparkles,
  urgent: CircleAlert,
  clients: UsersRound,
  impact: Target,
};

function formatMetric(metric) {
  return metric.kind === "currency"
    ? moneyFormat.format(metric.value)
    : numberFormat.format(metric.value);
}

function filterBySearch(items, fields, query) {
  return items.filter((item) =>
    fields.some((field) => String(item[field] ?? "").toLocaleLowerCase("fr").includes(query)),
  );
}

function DashboardPage() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState("6 mois");
  const [noticeVisible, setNoticeVisible] = useState(true);
  const { search = "" } = useOutletContext();

  useEffect(() => {
    const controller = new AbortController();
    getDashboardData({ signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setDashboard(data);
      })
      .catch((cause) => {
        if (cause.name !== "AbortError") setError("Le tableau de bord n’a pas pu être chargé. Réessayez.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const retryDashboard = async () => {
    setLoading(true);
    setError("");
    try {
      setDashboard(await getDashboardData());
    } catch {
      setError("Le tableau de bord n’a pas pu être chargé. Réessayez.");
    } finally {
      setLoading(false);
    }
  };

  const query = search.trim().toLocaleLowerCase("fr");
  const recentChanges = useMemo(
    () => dashboard ? filterBySearch(dashboard.recentChanges, ["title", "source", "device"], query) : [],
    [dashboard, query],
  );
  const priorityAlerts = useMemo(
    () => dashboard ? filterBySearch(dashboard.priorityAlerts, ["client", "subject", "urgency"], query) : [],
    [dashboard, query],
  );
  const actions = useMemo(
    () => dashboard ? filterBySearch(dashboard.actions, ["title", "client", "priority"], query) : [],
    [dashboard, query],
  );
  const reforms = useMemo(
    () => dashboard ? filterBySearch(dashboard.upcomingReforms, ["title", "source", "step"], query) : [],
    [dashboard, query],
  );
  const chartData = useMemo(
    () => period === "6 mois" ? dashboard?.changeHistory.slice(-6) : dashboard?.changeHistory,
    [dashboard, period],
  );

  if (loading && !dashboard) return <DashboardLoading />;
  if (error && !dashboard) {
    return (
      <section className="load-error" role="alert">
        <CircleAlert size={20} />
        <p>{error}</p>
        <button className="button button-outline" onClick={retryDashboard}>
          <RefreshCw size={15} /> Réessayer
        </button>
      </section>
    );
  }
  if (!dashboard) return null;

  return (
    <div className="dashboard-page">
      <div className="page-heading dashboard-heading">
        <div>
          <span className="eyebrow"><span className="eyebrow-mark" /> VOTRE ESPACE CONSULTANT</span>
          <h1>Bonjour {dashboard.consultant.name} <span className="greeting-wave">👋</span></h1>
          <p>Voici les évolutions réglementaires à suivre pour votre portefeuille.</p>
        </div>
        <div className="date-filter" aria-label="Date du tableau de bord">
          <CalendarDays size={16} />
          <span>25 novembre 2026</span>
        </div>
      </div>

      {noticeVisible && (
        <div className="dashboard-notice">
          <Info size={15} />
          <span>Les indicateurs présentés sont des données de démonstration.</span>
          <button aria-label="Masquer l’information" onClick={() => setNoticeVisible(false)}><Check size={14} /></button>
        </div>
      )}

      {error && <div className="inline-error" role="status">{error}</div>}

      <section className="metric-grid" aria-label="Indicateurs clés">
        {dashboard.metrics.map((metric) => {
          const Icon = metricIcons[metric.id];
          return (
            <article className={`metric-card metric-${metric.id}`} key={metric.id}>
              <div className="metric-card-top">
                <span className={`metric-icon metric-icon-${metric.id}`}><Icon size={18} strokeWidth={1.8} /></span>
                <span className={`metric-trend${metric.tone === "urgent" ? " trend-alert" : ""}`}>
                  <ArrowUpRight size={13} /> {metric.change}
                </span>
              </div>
              <p>{metric.label}</p>
              <strong>{formatMetric(metric)}</strong>
            </article>
          );
        })}
      </section>

      <section className="dashboard-grid">
        <article className="panel trend-panel">
          <div className="panel-heading">
            <div>
              <h2>Évolutions réglementaires</h2>
              <p>Changements confirmés et réformes anticipées</p>
            </div>
            <label className="select-wrap">
              <span className="sr-only">Période du graphique</span>
              <select value={period} onChange={(event) => setPeriod(event.target.value)}>
                <option>6 mois</option>
                <option>12 mois</option>
              </select>
              <ChevronDown size={14} />
            </label>
          </div>
          <div className="chart-legend">
            <span><i className="legend-dot confirmed-dot" /> Confirmés</span>
            <span><i className="legend-dot anticipated-dot" /> Anticipés</span>
          </div>
          <div className="chart-wrap">
            <Suspense fallback={<div className="chart-loading">Chargement du graphique…</div>}>
              <RegulatoryTrendChart data={chartData} />
            </Suspense>
          </div>
          <div className="chart-footnote"><span><Info size={13} /> Données illustratives</span><Link to="/veille">Explorer la veille <ArrowRight size={14} /></Link></div>
        </article>

        <article className="panel reforms-panel">
          <div className="panel-heading">
            <div>
              <h2>Réformes à surveiller</h2>
              <p>Signaux législatifs en cours</p>
            </div>
            <Link className="icon-link" to="/reformes" aria-label="Voir toutes les réformes"><ArrowRight size={17} /></Link>
          </div>
          <div className="reform-list">
            {reforms.length ? reforms.map((reform) => (
              <div className="reform-item" key={reform.id}>
                <div className="reform-status"><span /></div>
                <div className="reform-content">
                  <div className="reform-meta"><span className="forecast-tag">Prévision</span><span>{reform.source}</span></div>
                  <h3>{reform.title}</h3>
                  <p><span>{reform.step}</span><span className="reform-clients">{reform.clients} clients</span></p>
                  <div className="probability-row">
                    <span>Probabilité estimée</span><strong>{reform.probability}%</strong>
                  </div>
                  <div className="probability-track"><span style={{ width: `${reform.probability}%` }} /></div>
                </div>
              </div>
            )) : <EmptyPanel text={query ? "Aucune réforme ne correspond à la recherche." : "Aucune réforme à surveiller."} />}
          </div>
          <Link className="panel-bottom-link" to="/reformes">Voir les réformes anticipées <ArrowRight size={14} /></Link>
        </article>
      </section>

      <section className="dashboard-grid lower-grid">
        <article className="panel changes-panel">
          <div className="panel-heading">
            <div>
              <h2>Dernières évolutions</h2>
              <p>Les nouveautés qui concernent vos dispositifs</p>
            </div>
            <Link className="text-link" to="/veille">Tout voir <ArrowRight size={14} /></Link>
          </div>
          <div className="change-list">
            {recentChanges.length ? recentChanges.map((change) => (
              <Link className="change-row" to={`/veille/${change.id}`} key={change.id}>
                <span className="change-file-icon"><FileText size={17} /></span>
                <span className="change-main">
                  <strong>{change.title}</strong>
                  <span className="change-subline">{change.source}<i />{change.date}</span>
                </span>
                <span className="change-tags">
                  <span className="device-pill">{change.device}</span>
                  <span className={`status-pill status-${change.statusType}`}><i />{change.status}</span>
                </span>
                <ArrowRight className="change-arrow" size={16} />
              </Link>
            )) : <EmptyPanel text={query ? "Aucune évolution ne correspond à la recherche." : "Aucune évolution récente."} />}
          </div>
          <Link className="panel-bottom-link" to="/veille">Consulter toute la veille <ArrowRight size={14} /></Link>
        </article>

        <article className="panel alerts-panel">
          <div className="panel-heading">
            <div>
              <h2>Alertes prioritaires</h2>
              <p>À examiner en priorité</p>
            </div>
            <Link className="alert-count-link" to="/alertes">{dashboard.priorityAlerts.length} alertes <ArrowRight size={14} /></Link>
          </div>
          <div className="priority-list">
            {priorityAlerts.length ? priorityAlerts.map((alert) => (
              <Link className="priority-row" to="/alertes" key={alert.id}>
                <span className={`priority-mark ${alert.urgency === "Urgente" ? "priority-mark-urgent" : ""}`} />
                <span className="priority-main">
                  <strong>{alert.client}</strong>
                  <span>{alert.subject}</span>
                  <small><Clock3 size={12} /> {alert.deadline}</small>
                </span>
                <span className="priority-value">
                  <strong>{moneyFormat.format(alert.amount)}</strong>
                  <small className={alert.urgency === "Urgente" ? "urgent-text" : ""}>{alert.urgency}</small>
                </span>
              </Link>
            )) : <EmptyPanel text={query ? "Aucune alerte ne correspond à la recherche." : "Aucune alerte prioritaire."} />}
          </div>
          <Link className="panel-bottom-link" to="/alertes">Accéder à mes alertes <ArrowRight size={14} /></Link>
        </article>
      </section>

      <section className="panel action-panel">
        <div className="panel-heading">
          <div>
            <h2>Actions à réaliser</h2>
            <p>Vos prochaines étapes recommandées</p>
          </div>
          <Link className="text-link" to="/actions">Toutes les actions <ArrowRight size={14} /></Link>
        </div>
        <div className="action-grid">
          {actions.length ? actions.map((action) => (
            <Link className="action-card" to="/actions" key={action.id}>
              <span className="action-card-icon"><Target size={17} /></span>
              <span className={`action-deadline deadline-${action.priorityType}`}>{action.priorityType === "today" && <i />}{action.priority}</span>
              <strong>{action.title}</strong>
              <span className="action-client">{action.client}</span>
              <span className="action-link">Consulter l’action <ArrowRight size={13} /></span>
            </Link>
          )) : <EmptyPanel text={query ? "Aucune action ne correspond à la recherche." : "Aucune action à réaliser."} />}
        </div>
      </section>

      <footer className="dashboard-footer">
        <span>LEYpilot · Espace consultant Leyton</span>
        <span>Données de démonstration — les prévisions sont indicatives.</span>
      </footer>
    </div>
  );
}

function EmptyPanel({ text }) {
  return <div className="empty-panel">{text}</div>;
}

function DashboardLoading() {
  return (
    <div className="dashboard-page loading-dashboard" aria-label="Chargement du tableau de bord">
      <div className="skeleton skeleton-heading" />
      <div className="skeleton-metrics">{Array.from({ length: 6 }, (_, index) => <div className="skeleton skeleton-metric" key={index} />)}</div>
      <div className="skeleton-main"><div className="skeleton skeleton-panel" /><div className="skeleton skeleton-panel" /></div>
    </div>
  );
}

export default DashboardPage;
