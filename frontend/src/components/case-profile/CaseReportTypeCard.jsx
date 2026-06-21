import { ClinicalProgressBar } from '../clinical-ui/ClinicalProgressBar.jsx'
import { ClinicalStatusBadge } from '../clinical-ui/ClinicalStatusBadge.jsx'

function progressForStatus(status) {
  const s = String(status || '').toLowerCase()
  if (['published', 'approved', 'complete', 'completed'].includes(s)) return 100
  if (['under_review', 'submitted', 'in_review'].includes(s)) return 70
  if (['draft', 'in_progress'].includes(s)) return 40
  if (['rejected'].includes(s)) return 25
  return 15
}

export function CaseReportTypeCard({
  title,
  subtitle,
  status,
  statusLabel,
  progress,
  alert,
  meta,
  ctaLabel = 'Open',
  onOpen,
}) {
  const resolvedProgress = progress ?? progressForStatus(status)
  const badgeStatus = statusLabel || status || 'Not started'

  return (
    <article className="cp-report-type-card">
      <header className="cp-report-type-card__header">
        <div>
          <h3 className="cp-report-type-card__title">{title}</h3>
          {subtitle ? <p className="cp-report-type-card__subtitle">{subtitle}</p> : null}
        </div>
        <ClinicalStatusBadge status={status} customLabel={badgeStatus} />
      </header>

      <ClinicalProgressBar
        pct={resolvedProgress}
        label={meta || 'Documentation progress'}
        showPct={false}
      />

      {alert ? (
        <p className="cp-report-type-card__alert" role="status">{alert}</p>
      ) : null}

      <footer className="cp-report-type-card__footer">
        <button type="button" className="clinical-text-action" onClick={onOpen}>
          {ctaLabel}
        </button>
      </footer>
    </article>
  )
}
