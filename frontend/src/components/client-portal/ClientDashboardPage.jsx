import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useParentHome } from '../../hooks/useParentHome.js'
import { QueryState } from '../shared/QueryState.jsx'
import { formatDisplayDateLabel } from '../../lib/datetime.js'
import { upcomingAppointmentsForDashboard } from '../../lib/parentCases.js'
import { ParentAttendanceAlerts } from './ParentAttendanceAlerts.jsx'
import { ParentTherapistChat } from './ParentTherapistChat.jsx'
import './parent-dashboard.css'

function formatUpdateSessionWhen(update) {
  const parts = []
  if (update.scheduled_date) {
    parts.push(formatDisplayDateLabel(update.scheduled_date))
  }
  if (update.session_start_time) {
    parts.push(update.session_start_time)
  } else if (update.submitted_at) {
    try {
      parts.push(
        new Date(update.submitted_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }),
      )
    } catch {
      /* ignore */
    }
  }
  return parts.join(' · ')
}

function UpcomingSessionsSection({ appointments }) {
  const navigate = useNavigate()
  const upcoming = upcomingAppointmentsForDashboard(appointments, 2)
  return (
    <section className="parent-dash-section">
      <div className="parent-dash-section__head">
        <h2 className="parent-dash-section__title">Upcoming sessions &amp; meetings</h2>
        <div className="parent-dash-section__links">
          <Link to="/parent/book" className="parent-dash-section__link">
            Sessions →
          </Link>
          <Link to="/parent/meetings" className="parent-dash-section__link">
            Meetings →
          </Link>
        </div>
      </div>
      {upcoming.length === 0 ? (
        <p className="parent-dash-muted">
          Nothing scheduled yet.{' '}
          <Link to="/parent/book">Book a session</Link> or check{' '}
          <Link to="/parent/meetings">meetings</Link> your clinic has set up.
        </p>
      ) : (
        <ul className="parent-dash-session-list">
          {upcoming.map((appt) => (
            <li key={appt.id}>
              <button
                type="button"
                className={`parent-next-session__card parent-dash-session-list__card${appt.isCmMeeting ? ' parent-dash-session-list__card--meeting' : ''}`}
                onClick={() => {
                  if (appt.isCmMeeting) {
                    navigate('/parent/meetings', { state: { meetingId: appt.rawId } })
                    return
                  }
                  navigate('/parent/book', { state: { openApptId: appt.id } })
                }}
              >
                <div className="parent-next-session__when">
                  <strong>{formatDisplayDateLabel(appt.slotDate)}</strong>
                  <span>
                    {appt.startTime}
                    {appt.endTime ? `–${appt.endTime}` : ''}
                  </span>
                </div>
                <div className="parent-next-session__detail">
                  <p className="parent-next-session__title">
                    {appt.isCmMeeting
                      ? appt.meetingTitle || 'Case manager meeting'
                      : appt.childName || 'Therapy session'}
                  </p>
                  <p className="parent-next-session__meta">
                    {appt.isCmMeeting
                      ? [appt.caseMgrName || 'Case manager', appt.childName].filter(Boolean).join(' · ')
                      : [appt.therapistName, appt.childName].filter(Boolean).join(' · ')}
                  </p>
                  {appt.isCmMeeting ? (
                    <span className="parent-dash-session-list__badge">Clinic meeting</span>
                  ) : null}
                </div>
                <span className="parent-next-session__chevron" aria-hidden>
                  →
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function SessionLogsStatusSection({ logs }) {
  if (!logs?.length) return null
  return (
    <section className="parent-dash-section">
      <div className="parent-dash-section__head">
        <h2 className="parent-dash-section__title">Session logs</h2>
        <Link to="/parent/session-logs" className="parent-dash-section__link">
          View all →
        </Link>
      </div>
      <ul className="parent-dash-status-list">
        {logs.map((u) => {
          const when = formatUpdateSessionWhen(u)
          const status = u.parent_display_status || 'Pending review'
          return (
            <li key={u.id}>
              <Link to={`/parent/session-logs?log_id=${u.id}`} className="parent-dash-status-list__row">
                <span className="parent-dash-status-list__main">
                  <span className="parent-dash-status-list__label">
                    {u.child_name || 'Session'} · {when || 'Recent'}
                  </span>
                </span>
                <span className="parent-dash-status parent-dash-status--review">{status}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

function PendingInvoiceBanner({ billingSummary }) {
  const overdue = billingSummary?.overdueCount > 0
  const due = billingSummary?.needsPaymentCount > 0
  if (!overdue && !due) return null
  const count = overdue ? billingSummary.overdueCount : billingSummary.needsPaymentCount
  const label = overdue ? 'Overdue invoice' : 'Payment due'
  const amount =
    billingSummary.dueTotalInr > 0
      ? ` · ₹${Number(billingSummary.dueTotalInr).toLocaleString('en-IN')}`
      : ''
  return (
    <Link to="/parent/billing" className="parent-dash-invoice-alert">
      <span className="parent-dash-invoice-alert__label">{label}</span>
      <span className="parent-dash-invoice-alert__detail">
        {count} invoice{count === 1 ? '' : 's'}
        {amount}
      </span>
      <span className="parent-dash-invoice-alert__cta">Pay →</span>
    </Link>
  )
}

function PendingAssignmentBanner({ items, onAccepted }) {
  const [busyId, setBusyId] = useState(null)
  const [err, setErr] = useState('')
  if (!items?.length) return null
  return (
    <section
      className="card"
      style={{
        marginBottom: 20,
        padding: 16,
        border: '1px solid #c7d2fe',
        background: 'linear-gradient(135deg, #eef2ff 0%, #f8fafc 100%)',
      }}
    >
      <h2 style={{ margin: '0 0 8px', fontSize: '1rem', fontWeight: 700, color: '#312e81' }}>
        New care assignment
      </h2>
      <p style={{ margin: '0 0 12px', fontSize: '0.875rem', color: '#475569' }}>
        Your therapist and schedule are ready to use. Please review the plan when you can — accepting is optional
        for now and helps us know you have seen the details.
      </p>
      {err ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{err}</p> : null}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {items.map((item) => (
          <li
            key={item.assignment_id}
            style={{
              padding: 12,
              borderRadius: 10,
              background: '#fff',
              border: '1px solid #e2e8f0',
            }}
          >
            <p style={{ margin: '0 0 4px', fontWeight: 600 }}>
              {item.child_name} · {item.case_code}
            </p>
            {item.therapist_name ? (
              <p style={{ margin: '0 0 10px', fontSize: '0.875rem', color: '#64748b' }}>
                Therapist: {item.therapist_name}
              </p>
            ) : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <button
                type="button"
                className="admin-btn admin-btn--primary admin-btn--sm"
                disabled={busyId === item.assignment_id}
                onClick={async () => {
                  setBusyId(item.assignment_id)
                  setErr('')
                  try {
                    await apiFetch(`/api/v1/parent/assignments/${item.assignment_id}/accept`, {
                      method: 'POST',
                    })
                    onAccepted?.()
                  } catch (e) {
                    setErr(e.message || 'Could not accept assignment')
                  } finally {
                    setBusyId(null)
                  }
                }}
              >
                {busyId === item.assignment_id ? 'Saving…' : 'I have reviewed this assignment'}
              </button>
              <Link
                to="/parent/support"
                state={{
                  prefill: {
                    topic: 'CASE_ISSUE',
                    subject: `Assignment question — ${item.case_code}`,
                    caseId: item.case_id,
                  },
                }}
                style={{ fontSize: '0.875rem', alignSelf: 'center', fontWeight: 600 }}
              >
                Report a problem
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function ClientDashboardPage({
  cases,
  iepItems,
  billingSummary,
  appointments,
  notifications = [],
}) {
  const { user } = useAuth()
  const { data: home, isLoading: homeLoading, isError, error, refetch } = useParentHome()
  const [activeTab, setActiveTab] = useState('overview') // overview | chat
  const stats = home?.stats
  const displayName = user?.full_name?.trim() || 'Your account'
  const unreadCount =
    stats?.unread_notifications ??
    (notifications || []).filter((n) => !n.isRead).length
  const homeCases = useMemo(() => {
    if (!home?.cases?.length) return cases || []
    return home.cases.map((c) => ({
      id: c.id,
      caseId: c.caseId,
      childName: c.childName,
      serviceType: c.serviceType,
      therapist: c.therapistName || '—',
      caseManager: c.caseManagerName || '—',
      latestApprovedReportMonth: c.latestApprovedReportMonth || '—',
    }))
  }, [home, cases])
  const logsUnderReview = home?.logs_under_review || []
  const pendingAcceptance = home?.pending_assignment_acceptance || []
  const pendingIepByChild = useMemo(() => {
    const map = new Map()
    for (const item of iepItems || []) {
      if (item.status === 'pending' && item.childName) {
        map.set(item.childName.toLowerCase(), item)
      }
    }
    return map
  }, [iepItems])

  return (
    <>
      <header className="parent-dashboard-greeting parent-dashboard-greeting--compact">
        <div className="parent-dashboard-top">
          <h1 className="parent-dashboard-greeting__title">{displayName}</h1>
          <Link
            to="/parent/notifications"
            className="parent-dashboard-bell"
            aria-label={unreadCount ? `${unreadCount} unread notifications` : 'Notifications'}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path
                d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 1 0-14 0v5l-2 2v1h18v-1l-2-2Z"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinejoin="round"
              />
            </svg>
            {unreadCount > 0 ? (
              <span className="parent-dashboard-bell__badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
            ) : null}
          </Link>
        </div>
        <div className="ic-session-log-tabs" style={{ marginTop: 12 }} role="tablist" aria-label="Dashboard views">
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
            aria-selected={activeTab === 'chat'}
            className={`ic-session-log-tabs__btn${activeTab === 'chat' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            Therapist chat
          </button>
        </div>
      </header>

      {activeTab === 'overview' ? (
        <>
          <QueryState
            isLoading={homeLoading}
            isError={isError}
            error={error}
            onRetry={() => refetch()}
          >
          <PendingAssignmentBanner items={pendingAcceptance} onAccepted={() => refetch()} />
          <PendingInvoiceBanner billingSummary={billingSummary} />

          <UpcomingSessionsSection appointments={appointments} />

          <section className="parent-dash-section">
            <div className="parent-dash-section__head">
              <h2 className="parent-dash-section__title">Leave &amp; absence</h2>
              <Link to="/parent/session-logs" className="parent-dash-section__link">
                Session logs →
              </Link>
            </div>
            <ParentAttendanceAlerts />
          </section>

          <SessionLogsStatusSection logs={logsUnderReview} />
          </QueryState>

          <section className="parent-dash-section">
            <div className="parent-dash-section__head">
              <h2 className="parent-dash-section__title">Your cases</h2>
            </div>
            {(homeCases || []).length === 0 ? (
              <p className="parent-dash-muted">No active cases on your account yet.</p>
            ) : (
              <ul className="parent-dash-case-list">
                {(homeCases || []).map((item) => {
                  const pendingIep = pendingIepByChild.get(item.childName?.toLowerCase())
                  return (
                    <li key={item.id} className="parent-dash-case-list__item">
                      <Link to={`/parent/cases/${item.id}`} className="parent-dash-case-list__main">
                        <span className="parent-dash-case-list__name">{item.childName}</span>
                        <span className="parent-dash-case-list__meta">
                          {item.therapist !== '—' ? item.therapist : 'Therapist pending'}
                        </span>
                      </Link>
                      <div className="parent-dash-case-list__actions">
                        <Link
                          to="/parent/notifications"
                          className="parent-dash-case-list__bell"
                          aria-label={`Notifications for ${item.childName}`}
                        >
                          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
                            <path
                              d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 1 0-14 0v5l-2 2v1h18v-1l-2-2Z"
                              stroke="currentColor"
                              strokeWidth="1.75"
                            />
                          </svg>
                          {unreadCount > 0 ? (
                            <span className="parent-dash-case-list__bell-badge" aria-hidden />
                          ) : null}
                        </Link>
                        {pendingIep ? (
                          <Link to={`/parent/cases/${item.id}?tab=iep`} className="parent-dash-case-list__chip">
                            IEP review
                          </Link>
                        ) : null}
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        </>
      ) : (
        <ParentTherapistChat cases={homeCases} />
      )}
    </>
  )
}
