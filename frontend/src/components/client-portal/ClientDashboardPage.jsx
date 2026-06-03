import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useParentHome } from '../../hooks/useParentHome.js'
import { QueryState } from '../shared/QueryState.jsx'
import './parent-dashboard.css'

function fmt(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

function formatUpdateSessionWhen(update) {
  const parts = []
  if (update.scheduled_date) {
    parts.push(fmt(update.scheduled_date))
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

function nextAppointment(appointments) {
  return [...(appointments || [])].sort((a, b) => {
    const da = `${a.slotDate}T${a.startTime || '00:00'}`
    const db = `${b.slotDate}T${b.startTime || '00:00'}`
    return da < db ? -1 : da > db ? 1 : 0
  })[0]
}

function NextUpcomingSessionCard({ appointments }) {
  const navigate = useNavigate()
  const appt = nextAppointment(appointments)
  if (!appt) {
    return (
      <section className="parent-next-session parent-next-session--empty">
        <p className="parent-next-session__empty">No upcoming sessions scheduled.</p>
        <Link to="/parent/book" className="parent-next-session__link">
          Book a session →
        </Link>
      </section>
    )
  }
  return (
    <section className="parent-next-session">
      <div className="parent-next-session__head">
        <span className="parent-next-session__eyebrow">Next session</span>
        <Link to="/parent/book" className="parent-next-session__link">
          Full schedule →
        </Link>
      </div>
      <button
        type="button"
        className="parent-next-session__card"
        onClick={() => navigate('/parent/book', { state: { openApptId: appt.id } })}
      >
        <div className="parent-next-session__when">
          <strong>{fmt(appt.slotDate)}</strong>
          <span>
            {appt.startTime}
            {appt.endTime ? `–${appt.endTime}` : ''}
          </span>
        </div>
        <div className="parent-next-session__detail">
          <p className="parent-next-session__title">
            {appt.isCmMeeting ? 'Case manager meeting' : appt.childName || 'Therapy session'}
          </p>
          <p className="parent-next-session__meta">
            {appt.isCmMeeting
              ? appt.caseMgrName || 'With your case manager'
              : [appt.therapistName, appt.childName].filter(Boolean).join(' · ')}
          </p>
        </div>
        <span className="parent-next-session__chevron" aria-hidden>
          →
        </span>
      </button>
    </section>
  )
}

function RecentUpdatesSection({ updates }) {
  if (!updates?.length) return null
  return (
    <section className="parent-recent-updates">
      <div className="parent-recent-updates__head">
        <h2>Recent session updates</h2>
        <Link to="/parent/session-logs" className="parent-recent-updates__link">
          View all →
        </Link>
      </div>
      <ul className="parent-update-list">
        {updates.map((u) => {
          const when = formatUpdateSessionWhen(u)
          const metaParts = [when, u.child_name, u.therapist_name].filter(Boolean)
          return (
            <li key={u.id}>
              <Link
                to={`/parent/cases/${u.case_id}?tab=sessions`}
                className="card parent-update-list__item parent-update-list__item--link"
              >
                <div className="parent-update-list__row">
                  <div className="parent-update-list__main">
                    <div className="parent-update-list__headline">{u.attendance_label || u.headline}</div>
                    {metaParts.length ? (
                      <p className="parent-update-list__meta">{metaParts.join(' · ')}</p>
                    ) : null}
                    {u.summary_paragraph ? (
                      <p className="parent-update-list__body">{u.summary_paragraph}</p>
                    ) : null}
                  </div>
                  <span className="parent-update-list__chevron" aria-hidden>
                    →
                  </span>
                </div>
              </Link>
            </li>
          )
        })}
      </ul>
    </section>
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

const NOTIFICATION_PREVIEW_COUNT = 3

function RecentNotificationsPanel({ notifications, onMarkRead }) {
  const [expanded, setExpanded] = useState(false)
  const list = notifications || []
  const hasMore = list.length > NOTIFICATION_PREVIEW_COUNT
  const visible = expanded ? list : list.slice(0, NOTIFICATION_PREVIEW_COUNT)

  return (
    <article className="card parent-notifications-panel">
      <div className="card-head parent-notifications-panel__head">
        <h3>Recent Notifications</h3>
        {list.length > 0 ? (
          <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600 }}>{list.length} total</span>
        ) : null}
      </div>
      <ul className="parent-notifications-panel__list">
        {list.length === 0 ? (
          <li className="parent-notifications-panel__item">No new notifications.</li>
        ) : (
          visible.map((n) => (
            <li
              key={n.id}
              className={`parent-notifications-panel__item${n.isRead ? '' : ' parent-notifications-panel__item--unread'}`}
            >
              <button type="button" onClick={() => onMarkRead?.(n.id)}>
                <strong>{n.title}</strong>
                {n.detail ? <p>{n.detail}</p> : null}
                {n.createdAt ? <time dateTime={n.createdAt}>{n.createdAt}</time> : null}
              </button>
            </li>
          ))
        )}
      </ul>
      {list.length > 0 ? (
        <div className="parent-notifications-panel__footer">
          {hasMore ? (
            <button
              type="button"
              className="parent-notifications-panel__toggle"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? 'Show less' : `View all (${list.length})`}
            </button>
          ) : null}
          <Link to="/parent/notifications" className="parent-notifications-panel__link">
            Open notifications page →
          </Link>
        </div>
      ) : null}
    </article>
  )
}

function ActionAlertsBanner({ billingSummary, pendingIepCount }) {
  const alerts = []

  if (billingSummary?.overdueCount > 0) {
    alerts.push({
      key: 'overdue',
      icon: '⚠',
      bg: '#fff7ed',
      border: '#fed7aa',
      iconColor: '#c2410c',
      textColor: '#7c2d12',
      message: `${billingSummary.overdueCount} invoice${billingSummary.overdueCount > 1 ? 's' : ''} overdue${billingSummary.dueTotalInr > 0 ? ` — ₹${Number(billingSummary.dueTotalInr).toLocaleString('en-IN')} balance past due` : ''}`,
      link: '/parent/billing',
      linkLabel: 'View payments',
    })
  } else if (billingSummary?.needsPaymentCount > 0) {
    alerts.push({
      key: 'due',
      icon: '💳',
      bg: '#eff6ff',
      border: '#bfdbfe',
      iconColor: '#1d4ed8',
      textColor: '#1e3a5f',
      message: `${billingSummary.needsPaymentCount} invoice${billingSummary.needsPaymentCount > 1 ? 's' : ''} awaiting payment${billingSummary.dueTotalInr > 0 ? ` — ₹${Number(billingSummary.dueTotalInr).toLocaleString('en-IN')} due` : ''}`,
      link: '/parent/billing',
      linkLabel: 'View payments',
    })
  }

  if (pendingIepCount > 0) {
    alerts.push({
      key: 'iep',
      icon: '📋',
      bg: '#f0fdf4',
      border: '#bbf7d0',
      iconColor: '#15803d',
      textColor: '#14532d',
      message: `${pendingIepCount} IEP acknowledgement${pendingIepCount > 1 ? 's' : ''} required`,
      link: '/parent/reports?type=iep',
      linkLabel: 'Review IEP',
    })
  }

  if (alerts.length === 0) return null

  return (
    <section style={{ marginBottom: 16 }} aria-label="Action required">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {alerts.map((a) => (
          <Link
            key={a.key}
            to={a.link}
            className="parent-action-alert card"
            style={{
              background: a.bg,
              border: `1px solid ${a.border}`,
              borderRadius: 12,
              padding: '10px 14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, minWidth: 0, flex: '1 1 auto' }}>
              <span style={{ fontSize: '1.1rem', flexShrink: 0 }} aria-hidden>
                {a.icon}
              </span>
              <span className="parent-action-alert__message" style={{ color: a.textColor }}>
                {a.message}
              </span>
            </div>
            <span className="parent-action-alert__cta" style={{ color: a.iconColor }}>
              {a.linkLabel} →
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}

export function ClientDashboardPage({
  cases,
  reports,
  iepItems,
  billing,
  billingSummary,
  appointments,
  notifications,
  onMarkRead,
  onMarkNotificationRead,
}) {
  const { user } = useAuth()
  const { data: home, isLoading: homeLoading, isError, error, refetch } = useParentHome()
  const stats = home?.stats
  const firstName = user?.full_name?.split(/\s+/)[0] || 'there'
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
  const recentUpdates = home?.recent_updates || []
  const pendingAcceptance = home?.pending_assignment_acceptance || []
  const highlight = homeCases?.[0]?.session_highlight
  const childLabel = homeCases?.[0]?.childName
  const pendingIepCount =
    stats?.pending_iep ?? (iepItems || []).filter((item) => item.status === 'pending').length
  const handleMarkRead = onMarkRead || onMarkNotificationRead
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
        <h1 className="parent-dashboard-greeting__title">Dear {firstName},</h1>
      </header>

      <QueryState
        isLoading={homeLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
      >
      <PendingAssignmentBanner items={pendingAcceptance} onAccepted={() => refetch()} />
      <ActionAlertsBanner billingSummary={billingSummary} pendingIepCount={pendingIepCount} />

      <NextUpcomingSessionCard appointments={appointments} />
      <RecentUpdatesSection updates={recentUpdates} />

      {highlight ? (
        <section className="parent-home-hero card" style={{ marginBottom: 20, padding: 20 }}>
          <p className="parent-home-hero__eyebrow">
            This week{childLabel ? ` with ${childLabel}` : ''}
          </p>
          <h2 style={{ margin: '0 0 8px', fontSize: '1.25rem' }}>{highlight.headline}</h2>
          {highlight.summary_paragraph ? (
            <p style={{ margin: 0, color: '#475569', lineHeight: 1.5 }}>{highlight.summary_paragraph}</p>
          ) : null}
          {highlight.what_we_did && highlight.what_we_did !== highlight.summary_paragraph ? (
            <p style={{ margin: '10px 0 0', fontSize: '0.875rem', color: '#334155' }}>
              <strong style={{ display: 'block', fontSize: '0.72rem', color: '#64748b', marginBottom: 4 }}>
                What we did today
              </strong>
              {highlight.what_we_did}
            </p>
          ) : null}
          {highlight.what_is_next ? (
            <p style={{ margin: '10px 0 0', fontSize: '0.875rem', color: '#334155' }}>
              <strong style={{ display: 'block', fontSize: '0.72rem', color: '#64748b', marginBottom: 4 }}>
                What&apos;s next
              </strong>
              {highlight.what_is_next}
            </p>
          ) : null}
          <Link to="/parent/session-logs" style={{ display: 'inline-block', marginTop: 12, fontWeight: 600 }}>
            All session updates →
          </Link>
        </section>
      ) : null}
      </QueryState>

      {stats ? (
        <section className="parent-dashboard-hero" aria-label="Current progress">
          <p className="parent-dashboard-hero__label">Current progress</p>
          <p className="parent-dashboard-hero__count">
            {stats.case_count} active case{stats.case_count === 1 ? '' : 's'}
          </p>
          <p className="parent-dashboard-hero__meta">
            {recentUpdates.length > 0
              ? `${recentUpdates.length} recent session update${recentUpdates.length === 1 ? '' : 's'}`
              : 'Session updates and reports appear here after your therapist logs a visit.'}
            {pendingIepCount > 0
              ? ` · ${pendingIepCount} IEP review${pendingIepCount === 1 ? '' : 's'} pending`
              : ''}
          </p>
          <Link
            to={homeCases[0] ? `/parent/cases/${homeCases[0].id}` : '/parent/session-logs'}
            className="parent-dashboard-hero__cta"
          >
            View all details
          </Link>
        </section>
      ) : null}

      {stats ? (
        <section className="parent-dashboard-stats" aria-label="Family summary">
          <ul className="parent-dashboard-stats__grid">
            <li>
              <div className="parent-dashboard-stats__tile">
                <strong>{stats.case_count}</strong>
                <span>Active cases</span>
              </div>
            </li>
            <li>
              <Link to="/parent/session-logs" className="parent-dashboard-stats__tile parent-dashboard-stats__tile--updates">
                <strong>{recentUpdates.length}</strong>
                <span>Recent updates</span>
              </Link>
            </li>
            <li>
              <Link to="/parent/reports?type=iep" className="parent-dashboard-stats__tile parent-dashboard-stats__tile--iep">
                <strong>{stats.pending_iep}</strong>
                <span>IEP pending</span>
              </Link>
            </li>
            <li>
              <Link to="/parent/notifications" className="parent-dashboard-stats__tile parent-dashboard-stats__tile--alerts">
                <strong>{stats.unread_notifications}</strong>
                <span>Unread alerts</span>
              </Link>
            </li>
          </ul>
        </section>
      ) : null}

      <section className="parent-dashboard-panel-grid">
        <article className="card">
          <div className="card-head">
            <h3>Your Active Cases</h3>
          </div>
          {(homeCases || []).length === 0 ? (
            <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>No active cases on your account yet.</p>
          ) : (
            <ul className="parent-case-card">
              {(homeCases || []).map((item) => {
                const pendingIep = pendingIepByChild.get(item.childName?.toLowerCase())
                return (
                  <li key={item.id} className="parent-case-card__item">
                    <div className="parent-case-card__head">
                      <div>
                        <p className="parent-case-card__name">
                          <Link to={`/parent/cases/${item.id}`}>{item.childName}</Link>
                        </p>
                        <span className="parent-case-card__code">{item.caseId}</span>
                      </div>
                      <span className="parent-case-card__tag">{item.serviceType}</span>
                    </div>
                    <p className="parent-case-card__meta">
                      Therapist: {item.therapist}
                      <br />
                      Case manager: {item.caseManager}
                      <br />
                      Latest approved report: {item.latestApprovedReportMonth}
                    </p>
                    <div className="parent-case-card__actions">
                      <Link to="/parent/reports" className="parent-case-card__btn parent-case-card__btn--outline">
                        Latest report
                      </Link>
                      {pendingIep ? (
                        <Link
                          to="/parent/reports?type=iep"
                          className="parent-case-card__btn parent-case-card__btn--primary"
                        >
                          Review IEP
                        </Link>
                      ) : null}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </article>

        <RecentNotificationsPanel notifications={notifications} onMarkRead={handleMarkRead} />
      </section>
    </>
  )
}
