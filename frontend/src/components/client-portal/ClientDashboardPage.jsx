import { Link } from 'react-router-dom'
import { useParentDashboardStats } from '../../hooks/useParentDashboardStats.js'

export function ClientDashboardPage({ cases, reports, iepItems, notifications, onMarkNotificationRead }) {
  const { stats, loading: statsLoading } = useParentDashboardStats()
  const pendingIepCount = iepItems.filter((item) => item.status === 'pending').length

  return (
    <>
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
              <Link to="/parent/iep">
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
          <p className="kpi-value">{cases.length}</p>
          <p className="kpi-meta">Mapped to your account only</p>
        </article>
        <article className="card kpi-card">
          <p className="kpi-title">Approved Reports</p>
          <p className="kpi-value">{reports.length}</p>
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
            {cases.map((item) => (
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
            {notifications.length === 0 ? (
              <li>No new notifications.</li>
            ) : (
              notifications.map((n) => (
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
                    onClick={() => onMarkNotificationRead?.(n.id)}
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
