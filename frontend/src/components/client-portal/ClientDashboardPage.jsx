import { Link } from 'react-router-dom'
import { useParentDashboardStats } from '../../hooks/useParentDashboardStats.js'

function fmt(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

function StatusBadge({ status }) {
  if (status === 'PENDING_THERAPIST') {
    return (
      <span
        style={{
          display: 'inline-block',
          fontSize: '0.7rem',
          fontWeight: 600,
          color: '#92400e',
          background: '#fef3c7',
          border: '1px solid #fde68a',
          borderRadius: 99,
          padding: '1px 8px',
          marginLeft: 6,
          verticalAlign: 'middle',
        }}
      >
        Pending approval
      </span>
    )
  }
  if (status === 'CANCELLED') {
    return (
      <span
        style={{
          display: 'inline-block',
          fontSize: '0.7rem',
          fontWeight: 600,
          color: '#991b1b',
          background: '#fee2e2',
          border: '1px solid #fca5a5',
          borderRadius: 99,
          padding: '1px 8px',
          marginLeft: 6,
          verticalAlign: 'middle',
        }}
      >
        Cancelled
      </span>
    )
  }
  return null
}

function UpcomingSessionsStrip({ appointments }) {
  const next5 = [...(appointments || [])]
    .sort((a, b) => {
      const da = a.slotDate + 'T' + (a.startTime || '00:00')
      const db = b.slotDate + 'T' + (b.startTime || '00:00')
      return da < db ? -1 : da > db ? 1 : 0
    })
    .slice(0, 5)

  return (
    <section style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', margin: 0 }}>Upcoming sessions</h2>
        <Link
          to="/parent/book"
          style={{ fontSize: '0.8rem', color: '#4f46e5', fontWeight: 600, textDecoration: 'none' }}
        >
          View schedule →
        </Link>
      </div>

      {next5.length === 0 ? (
        <div
          style={{
            background: '#f8fafc',
            border: '1px dashed #cbd5e1',
            borderRadius: 12,
            padding: '16px 20px',
            textAlign: 'center',
          }}
        >
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>No upcoming sessions.</p>
          <Link
            to="/parent/book"
            style={{
              display: 'inline-block',
              marginTop: 8,
              fontSize: '0.8rem',
              fontWeight: 600,
              color: '#4f46e5',
              textDecoration: 'none',
            }}
          >
            Book a session →
          </Link>
        </div>
      ) : (
        <div
          style={{
            display: 'flex',
            gap: 12,
            overflowX: 'auto',
            paddingBottom: 4,
          }}
        >
          {next5.map((appt) => (
            <div
              key={appt.id}
              style={{
                flex: '0 0 auto',
                minWidth: 190,
                maxWidth: 220,
                background: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: 14,
                padding: '12px 14px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
              }}
            >
              <p style={{ margin: '0 0 4px', fontSize: '0.75rem', fontWeight: 700, color: '#4f46e5', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                {fmt(appt.slotDate)}
              </p>
              <p style={{ margin: '0 0 2px', fontSize: '0.875rem', fontWeight: 600, color: '#1e293b' }}>
                {appt.startTime}
                {appt.endTime ? `–${appt.endTime}` : ''}
                <StatusBadge status={appt.approvalStatus} />
              </p>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#64748b' }}>{appt.childName}</p>
              {appt.therapistName ? (
                <p style={{ margin: '2px 0 0', fontSize: '0.75rem', color: '#94a3b8' }}>{appt.therapistName}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </section>
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
          <div
            key={a.key}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              background: a.bg,
              border: `1px solid ${a.border}`,
              borderRadius: 12,
              padding: '10px 14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
              <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>{a.icon}</span>
              <span style={{ fontSize: '0.875rem', fontWeight: 500, color: a.textColor, lineHeight: 1.4 }}>
                {a.message}
              </span>
            </div>
            <Link
              to={a.link}
              style={{
                flexShrink: 0,
                fontSize: '0.8rem',
                fontWeight: 700,
                color: a.iconColor,
                textDecoration: 'none',
                whiteSpace: 'nowrap',
              }}
            >
              {a.linkLabel} →
            </Link>
          </div>
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
  const { stats, loading: statsLoading } = useParentDashboardStats()
  const pendingIepCount = (iepItems || []).filter((item) => item.status === 'pending').length
  const handleMarkRead = onMarkRead || onMarkNotificationRead

  return (
    <>
      <ActionAlertsBanner billingSummary={billingSummary} pendingIepCount={pendingIepCount} />

      <UpcomingSessionsStrip appointments={appointments} />

      {!statsLoading && stats ? (
        <section className="therapist-dashboard-stats" aria-label="Family summary" style={{ marginBottom: 20 }}>
          <ul className="therapist-dashboard-stats__grid">
            <li>
              <strong>{stats.caseCount}</strong>
              <span>Active cases</span>
            </li>
            <li>
              <Link to="/parent/session-logs">
                <strong>{stats.sessionUpdates}</strong>
                <span>Session updates</span>
              </Link>
            </li>
            <li>
              <Link to="/parent/reports?type=iep">
                <strong>{stats.pendingIep}</strong>
                <span>IEP pending</span>
              </Link>
            </li>
            <li>
              <strong>{stats.unreadNotifications}</strong>
              <span>Unread alerts</span>
            </li>
          </ul>
        </section>
      ) : null}

      <section className="kpi-grid">
        <article className="card kpi-card">
          <p className="kpi-title">Active Cases</p>
          <p className="kpi-value">{(cases || []).length}</p>
          <p className="kpi-meta">Mapped to your account only</p>
        </article>
        <article className="card kpi-card">
          <p className="kpi-title">Approved Reports</p>
          <p className="kpi-value">{(reports || []).length}</p>
          <p className="kpi-meta">Visible after manager approval</p>
        </article>
        <article className="card kpi-card">
          <p className="kpi-title">IEP Pending</p>
          <p className="kpi-value">{pendingIepCount}</p>
          <p className="kpi-meta">Acknowledgement required</p>
        </article>
      </section>

      <section className="panel-grid">
        <article className="card">
          <div className="card-head">
            <h3>Your Active Cases</h3>
          </div>
          <ul className="log-list">
            {(cases || []).map((item) => (
              <li key={item.id}>
                <div>
                  <p>
                    <Link to={`/parent/cases/${item.id}`}>
                      {item.childName} ({item.caseId})
                    </Link>
                  </p>
                  <span>
                    {item.serviceType} · Therapist: {item.therapist}
                  </span>
                </div>
                <div>
                  <p>{item.latestApprovedReportMonth}</p>
                  <span>Latest approved report</span>
                </div>
              </li>
            ))}
          </ul>
        </article>

        <article className="card">
          <div className="card-head">
            <h3>Recent Notifications</h3>
          </div>
          <ul className="alerts-list">
            {(notifications || []).length === 0 ? (
              <li>No new notifications.</li>
            ) : (
              (notifications || []).map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      background: n.isRead ? 'transparent' : '#f0f9ff',
                      border: 'none',
                      padding: 8,
                      borderRadius: 8,
                      cursor: 'pointer',
                    }}
                    onClick={() => handleMarkRead?.(n.id)}
                  >
                    <strong>{n.title}</strong>
                    <p style={{ margin: '4px 0 0', fontSize: '0.875rem', color: '#6b7280' }}>{n.detail}</p>
                    <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{n.createdAt}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </article>
      </section>
    </>
  )
}
