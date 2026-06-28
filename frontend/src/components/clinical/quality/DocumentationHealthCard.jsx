export function DocumentationHealthCard({ summary }) {
  if (!summary) return null
  const status = summary.documentation_status || 'in_progress'
  const risk = summary.risk_level || 'ok'
  const labels = {
    complete: 'Complete',
    in_progress: 'In progress',
    needs_revision: 'Needs revision',
    missing: 'Missing',
  }
  const riskLabels = { ok: 'On track', attention: 'Needs attention', urgent: 'Urgent' }

  const checklistItems = [
    { key: 'active_iep', label: 'Active IEP', done: !summary.missing_items?.includes('active_iep') },
    { key: 'observation_checklist', label: 'Observation checklist', done: !summary.missing_items?.includes('observation_checklist') },
    { key: 'monthly_report_current_month', label: 'Monthly report current month', done: !summary.missing_items?.includes('monthly_report_current_month') },
    { key: 'session_logs', label: 'Session logs', done: !summary.missing_items?.includes('session_logs') },
  ]

  return (
    <section className="clinical-quality-card" aria-labelledby="doc-health-title">
      <h3 id="doc-health-title" className="clinical-quality-card__title">Documentation health</h3>
      <div className="clinical-quality-card__metrics">
        <span className={`cp-quality-pill cp-quality-pill--${status}`}>{labels[status] || status}</span>
        <span className={`cp-quality-pill cp-quality-pill--risk-${risk}`}>{riskLabels[risk] || risk}</span>
      </div>
      <ul className="clinical-quality-card__checklist">
        {checklistItems.map((item) => (
          <li key={item.key} className={item.done ? 'is-done' : ''}>{item.label}</li>
        ))}
      </ul>
    </section>
  )
}
