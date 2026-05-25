import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTherapistFrequentActions } from '../hooks/useTherapistFrequentActions.js'
import { useTherapistHome } from '../hooks/useTherapistHome.js'
import { QueryState } from '../components/shared/QueryState.jsx'
import { formatScheduleWhen } from '../lib/therapistSchedule.js'
import { THERAPIST_ACTIONS } from '../lib/therapistActions.js'

export function TherapistDashboardPage() {
  const { user } = useAuth()
  const { data: home, isLoading, isError, error, refetch } = useTherapistHome()
  const { actions, personalized, trackClick } = useTherapistFrequentActions(4)
  const primary = actions[0]
  const secondary = actions.slice(1)

  const greeting = (() => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  })()

  const stats = home?.stats
  const active = home?.active_session
  const needsLog = home?.needs_log_sessions || []
  const schedule = home?.schedule_preview || []
  const criticalCases = (home?.cases_board?.allCases || []).filter((c) => c.critical).slice(0, 5)

  return (
    <>
      <header className="topbar therapist-dashboard__header">
        <div className="therapist-dashboard__intro">
          <p className="therapist-dashboard__eyebrow">{greeting}</p>
          <h2>
            {user?.full_name?.split(' ')[0] || 'there'}
            {home?.greeting_context ? ` — next: ${home.greeting_context}` : ''}
          </h2>
          <p>Today’s sessions, logs due, and cases that need you.</p>
        </div>
        {active ? (
          <Link to="/therapist/logs" className="therapist-dashboard__cta">
            Active session — open logs
          </Link>
        ) : needsLog[0] ? (
          <Link
            to={`/therapist/logs?session=${needsLog[0].id}`}
            className="therapist-dashboard__cta"
          >
            Submit log
          </Link>
        ) : primary ? (
          <Link
            to={primary.to}
            className="therapist-dashboard__cta"
            onClick={() => trackClick(primary.id)}
          >
            {primary.label}
          </Link>
        ) : null}
      </header>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
      >
        {stats ? (
          <section className="therapist-dashboard-stats" aria-label="Work summary">
            <ul className="therapist-dashboard-stats__grid">
              <li>
                <Link to="/therapist/cases">
                  <strong>{stats.case_count}</strong>
                  <span>Assigned cases</span>
                </Link>
              </li>
              <li>
                <Link to="/therapist/logs">
                  <strong>{stats.needs_log}</strong>
                  <span>Sessions need log</span>
                </Link>
              </li>
              <li>
                <Link to="/therapist/logs">
                  <strong>{stats.pending_logs}</strong>
                  <span>Logs pending approval</span>
                </Link>
              </li>
              <li>
                <Link to="/therapist/reports">
                  <strong>{stats.draft_reports}</strong>
                  <span>Report drafts</span>
                </Link>
              </li>
            </ul>
          </section>
        ) : null}

        {needsLog.length > 0 ? (
          <section className="therapist-home-panel" aria-labelledby="needs-log-title">
            <h3 id="needs-log-title">Needs log</h3>
            <ul className="therapist-home-list">
              {needsLog.map((s) => (
                <li key={s.id}>
                  <Link to={`/therapist/logs?session=${s.id}`}>
                    <strong>{s.child_name || s.case_code}</strong>
                    <span>
                      {s.scheduled_date} · {String(s.start_time || '').slice(0, 5)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {schedule.length > 0 ? (
          <section className="therapist-home-panel" aria-labelledby="today-schedule-title">
            <h3 id="today-schedule-title">Today’s schedule</h3>
            <ul className="therapist-home-list">
              {schedule.slice(0, 6).map((item) => (
                <li key={item.key}>
                  <span>
                    <strong>{item.childName || item.caseCode}</strong>
                    <span className="therapist-home-list__meta">
                      {formatScheduleWhen(item)} · {item.subtitle}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            <Link to="/therapist/logs" className="therapist-home-panel__link">
              Open session logs →
            </Link>
          </section>
        ) : null}

        {criticalCases.length > 0 ? (
          <section className="therapist-home-panel" aria-labelledby="attention-cases-title">
            <h3 id="attention-cases-title">Cases needing attention</h3>
            <ul className="therapist-home-list">
              {criticalCases.map((c) => (
                <li key={c.id}>
                  <Link to={`/therapist/cases/${c.id}`}>
                    <strong>{c.child}</strong>
                    <span>{c.nextDue}</span>
                  </Link>
                </li>
              ))}
            </ul>
            <Link to="/therapist/cases?stage=attention" className="therapist-home-panel__link">
              View all cases →
            </Link>
          </section>
        ) : null}
      </QueryState>

      <section className="therapist-quick-actions" aria-labelledby="therapist-shortcuts-title">
        <div className="therapist-quick-actions__head">
          <h3 id="therapist-shortcuts-title">More actions</h3>
          <p>
            {personalized
              ? 'Shortcuts ranked by what you use most often'
              : 'Popular shortcuts'}
          </p>
        </div>
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
