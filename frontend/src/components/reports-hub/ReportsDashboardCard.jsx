function initials(name) {
  const parts = String(name || '?').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

function avatarTone(name) {
  const code = String(name || '').split('').reduce((n, c) => n + c.charCodeAt(0), 0)
  const tones = ['sage', 'sky', 'sand', 'rose', 'mint']
  return tones[code % tones.length]
}

function statusMeta(item) {
  if (item.bucket === 'published' || item.status === 'published') {
    return { label: 'APPROVED', tone: 'approved' }
  }
  if (item.attentionType === 'not_started') {
    return { label: 'NOT STARTED', tone: 'warn' }
  }
  if (item.attentionType === 'rejected') {
    return { label: 'REVISION', tone: 'warn' }
  }
  if (item.status === 'under_review') {
    return { label: 'UNDER REVIEW', tone: 'review' }
  }
  return { label: 'DRAFT', tone: 'draft' }
}

function urgencyLabel(item) {
  if (item.attentionType === 'overdue') return 'OVERDUE'
  if (item.attentionType === 'not_started') return 'DUE SOON'
  if (item.attentionType === 'rejected') return 'ACTION NEEDED'
  if (item.dueInfo && /due/i.test(item.dueInfo)) return item.dueInfo.toUpperCase()
  return null
}

function progressPct(item) {
  if (item.bucket === 'published' || item.status === 'published') return 100
  if (item.status === 'under_review') return 95
  if (item.attentionType === 'not_started') return 12
  if (item.attentionType === 'rejected') return 45
  if (item.status === 'draft') return 82
  return 60
}

function handleCardKeyDown(e, onActivate) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    onActivate()
  }
}

function ctaLabel(item) {
  if (item.bucket === 'published' || item.status === 'published') return 'View report'
  if (item.isPlaceholder || item.attentionType === 'not_started') return 'Start draft'
  if (item.status === 'draft' || item.status === 'under_review') return 'Continue'
  return 'Open'
}

export function ReportsDashboardCard({ item, caseMeta, onViewReports }) {
  const status = statusMeta(item)
  const urgency = urgencyLabel(item)
  const pct = progressPct(item)
  const reportType = item.reportTypeLabel || 'MONTHLY REPORT'
  const cmName = caseMeta?.caseManagerName || 'Unassigned'
  const tone = avatarTone(item.child)
  const actionLabel = ctaLabel(item)

  function openReports() {
    onViewReports?.(item)
  }

  return (
    <article
      className="reports-dashboard-card reports-dashboard-card--interactive"
      role="button"
      tabIndex={0}
      onClick={openReports}
      onKeyDown={(e) => handleCardKeyDown(e, openReports)}
      aria-label={`${item.child}, ${reportType}, ${status.label}. ${actionLabel}.`}
    >
      <div className="reports-dashboard-card__head">
        <div className="reports-dashboard-card__identity">
          <span className={`reports-dashboard-card__avatar reports-dashboard-card__avatar--${tone}`} aria-hidden="true">
            {initials(item.child)}
          </span>
          <div className="reports-dashboard-card__identity-text">
            <p className="reports-dashboard-card__name">{item.child}</p>
            <p className="reports-dashboard-card__meta">
              {item.month ? `${item.month} · ` : ''}
              Case {item.caseId}
            </p>
          </div>
        </div>
        <div className="reports-dashboard-card__badges">
          {urgency ? (
            <span className="reports-dashboard-card__urgency">{urgency}</span>
          ) : null}
          <span className={`reports-dashboard-card__status reports-dashboard-card__status--${status.tone}`}>
            {status.label}
          </span>
        </div>
      </div>

      <p className="reports-dashboard-card__type">
        {reportType}
        {caseMeta?.service || caseMeta?.productModule
          ? ` · ${caseMeta.service || caseMeta.productModule}`
          : ''}
      </p>

      <div className="reports-dashboard-card__progress">
        <div className="reports-dashboard-card__progress-labels">
          <span>Completion</span>
          <span className="reports-dashboard-card__progress-pct">{pct}%</span>
        </div>
        <div className="reports-dashboard-card__progress-track">
          <span className="reports-dashboard-card__progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <p className="reports-dashboard-card__cm">
        <span className="material-symbols-outlined" aria-hidden="true">person</span>
        CM: {cmName}
      </p>

      <div className="reports-dashboard-card__footer">
        <p className="reports-dashboard-card__updated">
          Updated: {item.lastUpdated || item.month || '—'}
        </p>
        <span className="reports-dashboard-card__cta" aria-hidden="true">
          {actionLabel}
          <span className="material-symbols-outlined">arrow_forward</span>
        </span>
      </div>
    </article>
  )
}
