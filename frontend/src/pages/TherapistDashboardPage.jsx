import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useTherapistFrequentActions } from '../hooks/useTherapistFrequentActions.js'
import { useTherapistHome } from '../hooks/useTherapistHome.js'
import { QueryState } from '../components/shared/QueryState.jsx'
import { TherapistTodaySchedule } from '../components/therapist/TherapistTodaySchedule.jsx'
import { UpcomingMeetingsPanel } from '../components/shared/UpcomingMeetingsPanel.jsx'
import { formatDisplayDate, formatDisplayDateTime } from '../lib/datetime.js'
import { THERAPIST_ACTIONS } from '../lib/therapistActions.js'
import { TherapistTicketsPage } from '../components/therapist/TherapistTicketsPage.jsx'

export function TherapistDashboardPage() {
  const { user } = useAuth()
  const { data: home, isLoading, isError, error, refetch } = useTherapistHome()
  const { actions, personalized, trackClick } = useTherapistFrequentActions(4)
  const secondary = actions.slice(1)
  const [activeTab, setActiveTab] = useState('overview')

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
      icon: 'log',
    })),
    ...pendingCmMeetings.map((m) => ({
      key: `cm-${m.id}`,
      to: '/therapist/meetings',
      eyebrow: 'CM meeting notes',
      title: m.child_name || m.case_code || 'Client',
      meta: formatDisplayDateTime(m.scheduled_date, m.scheduled_time) || m.scheduled_date,
      tone: 'amber',
      icon: 'meeting',
    })),
  ]
  const [acceptBusy, setAcceptBusy] = useState(null)
  const [acceptErr, setAcceptErr] = useState('')

  return (
    <>
      <header className="topbar therapist-dashboard__header" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
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
        </div>

        <div className="ic-session-log-tabs" style={{ marginTop: 8 }} role="tablist" aria-label="Dashboard views">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'overview'}
            className={`ic-session-log-tabs__btn${activeTab === 'overview' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'updates'}
            className={`ic-session-log-tabs__btn${activeTab === 'updates' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('updates')}
          >
            Therapist Updates
          </button>
        </div>
      </header>

      {activeTab === 'overview' ? (
        <QueryState
          isLoading={isLoading}
          isError={isError}
          error={error}
          onRetry={() => refetch()}
        >
          {pendingAssignments.length > 0 ? (
            <section className="card" style={{ marginBottom: 16, padding: 16, borderColor: '#c7d2fe' }}>
              <h3 style={{ margin: '0 0 8px', fontSize: '1rem' }}>New case assignment</h3>
              <p className="admin-muted" style={{ margin: '0 0 12px' }}>
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
                      <span
                        className={`therapist-pending-action__icon therapist-pending-action__icon--${item.icon}`}
                        aria-hidden
                      />
                      <span className="therapist-pending-action__body">
                        <span className="therapist-pending-action__eyebrow">{item.eyebrow}</span>
                        <strong className="therapist-pending-action__title">{item.title}</strong>
                        <span className="therapist-pending-action__meta">{item.meta}</span>
                      </span>
                      <span className="therapist-pending-action__chevron" aria-hidden>
                        →
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <UpcomingMeetingsPanel
            title="Upcoming meetings"
            subtitle="Next 7 days"
            href="/therapist/meetings"
            variant="therapist"
            className="therapist-home-panel"
          />

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
      ) : (
        <div style={{ marginTop: 20 }}>
          <TherapistTicketsPage />
        </div>
      )}

      <section className="therapist-quick-actions" aria-labelledby="therapist-shortcuts-title">
        <div className="therapist-quick-actions__head">
          <h3 id="therapist-shortcuts-title">More actions</h3>
          <p>
            {pendingActions.length > 0
              ? `${pendingActions.length} pending item${pendingActions.length === 1 ? '' : 's'} need your attention`
              : personalized
                ? 'Shortcuts ranked by what you use most often'
                : 'Popular shortcuts'}
          </p>
        </div>
        {pendingActions.length > 0 ? (
          <ul className="therapist-quick-actions__grid" style={{ marginBottom: 12 }}>
            {pendingActions.slice(0, 4).map((item) => (
              <li key={`pending-${item.key}`}>
                <Link
                  to={item.to}
                  className={`therapist-quick-actions__tile therapist-quick-actions__tile--${item.tone}`}
                >
                  <span className="therapist-quick-actions__icon" aria-hidden>
                    {item.icon}
                  </span>
                  <span className="therapist-quick-actions__tile-body">
                    <strong>{item.eyebrow}</strong>
                    <span>{item.title} · {item.meta}</span>
                  </span>
                  <span className="therapist-quick-actions__badge">Pending</span>
                </Link>
              </li>
            ))}
          </ul>
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
