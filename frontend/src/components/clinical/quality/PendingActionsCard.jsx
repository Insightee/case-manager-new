import { Link } from 'react-router-dom'
import { ClinicalActionButton } from '../../clinical-ui/ClinicalActionButton.jsx'

export function PendingActionsCard({ summary, basePath }) {
  const actions = summary?.recommended_next_actions || []
  return (
    <section className="clinical-quality-card" aria-labelledby="actions-title">
      <h3 id="actions-title" className="clinical-quality-card__title">Recommended next actions</h3>
      {actions.length ? (
        <ol className="clinical-quality-card__checklist" style={{ listStyle: 'decimal', paddingLeft: '1.25rem' }}>
          {actions.map((action) => (
            <li key={action} style={{ display: 'list-item' }}>{action}</li>
          ))}
        </ol>
      ) : (
        <p className="clinical-quality-card__stat-label">No pending actions — documentation is up to date.</p>
      )}
      {basePath ? (
        <div style={{ marginTop: '0.75rem' }}>
          <ClinicalActionButton as={Link} to={`${basePath}?tab=reports`} variant="secondary">
            Open reports
          </ClinicalActionButton>
        </div>
      ) : null}
    </section>
  )
}
