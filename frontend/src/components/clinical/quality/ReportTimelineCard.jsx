import { ClinicalStatusBadge } from '../../clinical-ui/ClinicalStatusBadge.jsx'

export function ReportTimelineCard({ summary }) {
  const timeline = summary?.report_timeline || []
  const statuses = summary?.report_statuses || {}
  return (
    <section className="clinical-quality-card" aria-labelledby="timeline-title">
      <h3 id="timeline-title" className="clinical-quality-card__title">Report timeline</h3>
      <p className="clinical-quality-card__stat-label" style={{ marginBottom: '0.625rem' }}>
        Current month ({statuses.current_month || '—'}):{' '}
        <strong style={{ color: 'var(--clinical-text)' }}>{statuses.current_month_status || 'Not started'}</strong>
      </p>
      {timeline.length ? (
        <ul className="clinical-quality-card__checklist">
          {timeline.map((item) => (
            <li key={`${item.type}-${item.id}`} style={{ justifyContent: 'space-between' }}>
              <span>{item.month}</span>
              <ClinicalStatusBadge status={String(item.status).toLowerCase().replace(/\s+/g, '_')} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="clinical-quality-card__stat-label">No monthly reports yet.</p>
      )}
    </section>
  )
}
