import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useTherapistFrequentActions } from '../hooks/useTherapistFrequentActions.js'
import { useTherapistHome } from '../hooks/useTherapistHome.js'
import { QueryState } from '../components/shared/QueryState.jsx'
import { TherapistTodaySchedule } from '../components/therapist/TherapistTodaySchedule.jsx'
import { TherapistDashboardIcon } from '../components/therapist/TherapistDashboardIcon.jsx'
import { formatDisplayDate, formatDisplayDateTime } from '../lib/datetime.js'
import { THERAPIST_ACTIONS } from '../lib/therapistActions.js'
import '../styles/therapist-dashboard.css'

const STAT_CARDS = [
  { key: 'case_count', to: '/therapist/cases', label: 'Assigned cases', icon: 'groups', tone: 'forest' },
  { key: 'needs_log', to: '/therapist/logs', label: 'Sessions need log', icon: 'edit_note', tone: 'amber' },
  { key: 'pending_logs', to: '/therapist/logs', label: 'Logs pending approval', icon: 'pending_actions', tone: 'dark' },
  { key: 'draft_reports', to: '/therapist/reports', label: 'Report drafts', icon: 'description', tone: 'mint' },
]

function tileTone(tone) {
  return tone === 'primary' ? 'forest' : tone
}

export function TherapistDashboardPage() {
  const { user } = useAuth()
  const { data: home, isLoading, isError, error, refetch } = useTherapistHome()
  const { actions, personalized, trackClick } = useTherapistFrequentActions(4)
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
  const pendingAssignments = home?.pending_assignment_acceptance || []
  const pendingCmMeetings = home?.pending_cm_meetings || []
  const pendingActions = [
    ...needsLog.map((s) => ({
      key: `log-${s.id}`,
      to: `/therapist/logs?session=${s.id}`,
      eyebrow: 'Session log due',
      title: s.child_name || s.case_code || 'Client',
      meta: s.scheduled_date ? `Visit · ${formatDisplayDate(s.scheduled_date)}` : 'Completed visit',
      tone: 'primary',
      icon: 'edit_note',
    })),
    ...pendingCmMeetings.map((m) => ({
      key: `cm-${m.id}`,
      to: m.case_id ? `/therapist/meetings?case_id=${m.case_id}` : '/therapist/meetings',
      eyebrow: 'Submit meeting notes',
      title: m.child_name || m.case_code || m.title || 'Case manager meeting',
      meta: [formatDisplayDateTime(m.scheduled_date, m.scheduled_time), m.title]
        .filter(Boolean)
        .join(' · '),
      tone: 'forest',
      icon: 'event_note',
      badge: 'Notes due',
    })),
  ]
  const [acceptBusy, setAcceptBusy] = useState(null)
  const [acceptErr, setAcceptErr] = useState('')

  return (
    <div className="therapist-dashboard-page forest-light">
      <header className="therapist-dashboard__header">
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
        ) : null}
      </header>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
      >
        {pendingAssignments.length > 0 ? (
          <section className="therapist-assignment-card">
            <h3>New case assignment</h3>
            <p className="admin-muted" style={{ margin: '0 0 12px', fontSize: '0.875rem', color: '#64748b' }}>
              You can start sessions and logs for this case now. Please review the care plan when you can — marking
              reviewed is optional.
            </p>
            {acceptErr ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{acceptErr}</p> : null}
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {pendingAssignments.map((item) => (
                <li key={item.assignment_id} style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                  <span>
                    <strong>{item.child_name}</strong> · {item.case_code}
                    {!item.parent_accepted ? (
                      <span style={{ marginLeft: 8, fontSize: '0.75rem', color: '#92400e' }}>
                        Waiting for parent
                      </span>
                    ) : null}
                  </span>
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary admin-btn--sm"
                    disabled={acceptBusy === item.assignment_id}
                    onClick={async () => {
                      setAcceptBusy(item.assignment_id)
                      setAcceptErr('')
                      try {
                        await apiFetch(`/api/v1/assignments/${item.assignment_id}/accept`, {
                          method: 'POST',
                        })
                        refetch()
                      } catch (e) {
                        setAcceptErr(e.message || 'Could not accept')
                      } finally {
                        setAcceptBusy(null)
                      }
                    }}
                  >
                    {acceptBusy === item.assignment_id ? 'Saving…' : 'Mark as reviewed'}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {stats ? (
          <section className="therapist-dashboard-stats" aria-label="Work summary">
            <ul className="therapist-dashboard-stats__grid">
              {STAT_CARDS.map((card) => (
                <li key={card.key}>
                  <Link to={card.to} className="therapist-dashboard-stats__card">
                    <TherapistDashboardIcon name={card.icon} tone={card.tone} />
                    <div>
                      <p className="therapist-dashboard-stats__value">{stats[card.key] ?? 0}</p>
                      <p className="therapist-dashboard-stats__label">{card.label}</p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {pendingActions.length > 0 ? (
          <section className="therapist-home-panel" aria-labelledby="pending-actions-title">
            <h3 id="pending-actions-title">Pending actions</h3>
            <ul className="therapist-pending-actions">
              {pendingActions.map((item) => (
                <li key={item.key}>
                  <Link
                    to={item.to}
                    className={`therapist-pending-action therapist-pending-action--${item.tone}`}
                  >
                    <TherapistDashboardIcon
                      name={item.icon}
                      tone={item.tone === 'primary' ? 'forest' : item.tone === 'forest' ? 'amber' : tileTone(item.tone)}
                    />
                    <span className="therapist-pending-action__body">
                      <span className="therapist-pending-action__eyebrow">{item.eyebrow}</span>
                      <strong className="therapist-pending-action__title">{item.title}</strong>
                      <span className="therapist-pending-action__meta">{item.meta}</span>
                    </span>
                    {item.badge ? (
                      <span className="therapist-pending-action__badge">{item.badge}</span>
                    ) : (
                      <span className="therapist-pending-action__chevron" aria-hidden>
                        →
                      </span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {schedule.length > 0 ? (
          <section className="therapist-home-panel therapist-home-panel--schedule" aria-labelledby="today-schedule-title">
            <div className="therapist-home-panel__head">
              <h3 id="today-schedule-title">Today’s schedule</h3>
              <p className="therapist-home-panel__hint">Tap a visit to open logs or the case</p>
            </div>
            <TherapistTodaySchedule items={schedule} limit={8} />
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
          <h3 id="therapist-shortcuts-title">Shortcuts</h3>
          <p>
            {personalized
              ? 'Ranked by what you use most often'
              : 'Popular ways to get work done'}
          </p>
        </div>
        <ul className="therapist-quick-actions__grid">
          {secondary.map((action) => (
            <li key={action.id}>
              <Link
                to={action.to}
                className={`therapist-quick-actions__tile therapist-quick-actions__tile--${tileTone(action.tone)}`}
                onClick={() => trackClick(action.id)}
              >
                <TherapistDashboardIcon name={action.icon} tone={tileTone(action.tone)} />
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
                  <span className="material-symbols-outlined" aria-hidden="true">
                    {action.icon}
                  </span>
                  {action.label}
                </Link>
              </li>
            ))}
          </ul>
        </details>
      </section>
    </div>
  )
}
