import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTherapistDashboardStats } from '../hooks/useTherapistDashboardStats.js'
import { useTherapistFrequentActions } from '../hooks/useTherapistFrequentActions.js'
import { THERAPIST_ACTIONS } from '../lib/therapistActions.js'

export function TherapistDashboardPage() {
  const { user } = useAuth()
  const { actions, personalized, trackClick } = useTherapistFrequentActions(4)
  const { stats, loading: statsLoading } = useTherapistDashboardStats()
  const primary = actions[0]
  const secondary = actions.slice(1)

  const greeting = (() => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  })()

  return (
    <>
      <header className="topbar therapist-dashboard__header">
        <div className="therapist-dashboard__intro">
          <p className="therapist-dashboard__eyebrow">{greeting}</p>
          <h2>{user?.full_name?.split(' ')[0] || 'there'}</h2>
          <p>Your assigned cases and session work — pick up where you left off.</p>
        </div>
        {primary ? (
          <div className="topbar-actions">
            <Link
              to={primary.to}
              className="therapist-dashboard__cta"
              onClick={() => trackClick(primary.id)}
            >
              {primary.label}
            </Link>
          </div>
        ) : null}
      </header>

      {!statsLoading && stats ? (
        <section className="therapist-dashboard-stats" aria-label="Work summary">
          <ul className="therapist-dashboard-stats__grid">
            <li>
              <Link to="/therapist/cases">
                <strong>{stats.caseCount}</strong>
                <span>Assigned cases</span>
              </Link>
            </li>
            <li>
              <Link to="/therapist/logs">
                <strong>{stats.needsLog}</strong>
                <span>Sessions need log</span>
              </Link>
            </li>
            <li>
              <Link to="/therapist/logs">
                <strong>{stats.pendingLogs}</strong>
                <span>Logs pending approval</span>
              </Link>
            </li>
            <li>
              <Link to="/therapist/reports">
                <strong>{stats.draftReports}</strong>
                <span>Report drafts to finish</span>
              </Link>
            </li>
          </ul>
        </section>
      ) : null}

      <section className="therapist-quick-actions" aria-labelledby="therapist-shortcuts-title">
        <div className="therapist-quick-actions__head">
          <h3 id="therapist-shortcuts-title">Quick actions</h3>
          <p>
            {personalized
              ? 'Shortcuts ranked by what you use most often'
              : 'Popular shortcuts — order updates as you use the portal'}
          </p>
        </div>

        {primary ? (
          <Link
            to={primary.to}
            className={`therapist-quick-actions__hero therapist-quick-actions__hero--${primary.tone}`}
            onClick={() => trackClick(primary.id)}
          >
            <span className="therapist-quick-actions__icon" aria-hidden>
              {primary.icon}
            </span>
            <span className="therapist-quick-actions__hero-body">
              <span className="therapist-quick-actions__hero-label">
                {personalized && primary.useCount > 0 ? 'Most used' : 'Suggested'}
              </span>
              <strong>{primary.label}</strong>
              <span>{primary.description}</span>
            </span>
            <span className="therapist-quick-actions__arrow" aria-hidden>
              →
            </span>
          </Link>
        ) : null}

        <ul className="therapist-quick-actions__grid">
          {secondary.map((action) => (
            <li key={action.id}>
              <Link
                to={action.to}
                className={`therapist-quick-actions__tile therapist-quick-actions__tile--${action.tone}`}
                onClick={() => trackClick(action.id)}
              >
                <span className="therapist-quick-actions__icon" aria-hidden>
                  {action.icon}
                </span>
                <span className="therapist-quick-actions__tile-body">
                  <strong>{action.label}</strong>
                  <span>{action.description}</span>
                </span>
                {personalized && action.useCount > 0 ? (
                  <span className="therapist-quick-actions__badge" title="Times opened">
                    {action.useCount}×
                  </span>
                ) : null}
              </Link>
            </li>
          ))}
        </ul>

        <details className="therapist-quick-actions__more">
          <summary>All actions ({THERAPIST_ACTIONS.length})</summary>
          <ul className="therapist-quick-actions__more-list">
            {THERAPIST_ACTIONS.map((action) => (
              <li key={action.id}>
                <Link to={action.to} onClick={() => trackClick(action.id)}>
                  <span aria-hidden>{action.icon}</span>
                  {action.label}
                </Link>
              </li>
            ))}
          </ul>
        </details>
      </section>
    </>
  )
}
