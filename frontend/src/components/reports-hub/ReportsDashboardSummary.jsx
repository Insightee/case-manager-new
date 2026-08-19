const METRICS = [
  { key: 'draft', label: 'Active Drafts', icon: 'description', tone: 'mint' },
  { key: 'underReview', label: 'Pending Review', icon: 'pending_actions', tone: 'dark' },
  { key: 'published', label: 'Approved Today', icon: 'check_circle', tone: 'forest' },
  { key: 'total', label: 'Total Active Cases', icon: 'groups', tone: 'muted' },
]

const EMBEDDED_METRICS = [
  { key: 'draft', label: 'Active Drafts', icon: 'description', tone: 'mint' },
  { key: 'underReview', label: 'Pending Review', icon: 'pending_actions', tone: 'dark' },
  { key: 'published', label: 'Approved', icon: 'check_circle', tone: 'forest' },
  { key: 'overdue', label: 'Needs Attention', icon: 'error', tone: 'alert' },
]

export function ReportsDashboardSummary({ counts, embedded = false }) {
  const defs = embedded ? EMBEDDED_METRICS : METRICS
  return (
    <div className="reports-dashboard-summary" role="group" aria-label="Reports summary">
      {defs.map((m) => (
        <article key={m.key} className={`reports-dashboard-summary__card reports-dashboard-summary__card--${m.tone}`}>
          <span className={`material-symbols-outlined reports-dashboard-summary__icon`} aria-hidden="true">
            {m.icon}
          </span>
          <div>
            <p className="reports-dashboard-summary__value">{counts[m.key] ?? 0}</p>
            <p className="reports-dashboard-summary__label">{m.label}</p>
          </div>
        </article>
      ))}
    </div>
  )
}
