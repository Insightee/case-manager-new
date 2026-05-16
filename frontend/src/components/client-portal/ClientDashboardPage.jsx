import { ClientPortalLayout } from './ClientPortalLayout'

export function ClientDashboardPage({ cases, reports, iepItems, notifications }) {
  const pendingIepCount = iepItems.filter((item) => item.status === 'pending').length

  return (
    <ClientPortalLayout
      title="Client Dashboard"
      subtitle="View approved updates, IEP actions, and billing status for your child."
      actionLabel="Raise support request"
    >
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
              <li key={item.caseId}>
                <div>
                  <p>
                    {item.childName} ({item.caseId})
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
            {notifications.map((item) => (
              <li key={item.id}>
                <div>
                  <p>{item.title}</p>
                  <span>{item.detail}</span>
                </div>
                <small>{item.createdAt}</small>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </ClientPortalLayout>
  )
}
