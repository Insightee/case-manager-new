import { ClinicalMetricCard } from './ClinicalMetricCard.jsx'
import { ClinicalActionButton } from './ClinicalActionButton.jsx'

export function ClinicalEvidencePanel({ title = 'Evidence Summary', metrics = [], onViewDrive, viewDriveLabel = 'View Full Evidence Drive' }) {
  return (
    <aside className="clinical-evidence-panel">
      <h3 className="clinical-evidence-panel__title">{title}</h3>
      <div className="clinical-metric-grid" style={{ gridTemplateColumns: '1fr', marginBottom: '0.75rem' }}>
        {metrics.map((m) => (
          <ClinicalMetricCard key={m.label} count={m.count} label={m.label} icon={m.icon} />
        ))}
      </div>
      {onViewDrive ? (
        <ClinicalActionButton variant="ghost" onClick={onViewDrive}>{viewDriveLabel}</ClinicalActionButton>
      ) : null}
    </aside>
  )
}
