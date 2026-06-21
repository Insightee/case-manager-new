/**
 * Insight card.
 * severity: 'info' | 'attention' | 'urgent'
 * title, reason: strings
 * actionLabel, onAction: optional CTA (only shown if both present)
 */
export function ClinicalInsightCard({ severity = 'info', title, reason, actionLabel, onAction }) {
  const icons = { info: '💡', attention: '⚠️', urgent: '🔴' }

  return (
    <div className={`clinical-insight-card clinical-insight-card--${severity}`} role="alert">
      <span className="clinical-insight-card__icon" aria-hidden="true">{icons[severity]}</span>
      <div className="clinical-insight-card__body">
        {title ? <p className="clinical-insight-card__title">{title}</p> : null}
        {reason ? <p className="clinical-insight-card__reason">{reason}</p> : null}
        {actionLabel && onAction ? (
          <button type="button" className="clinical-insight-card__action" onClick={onAction}>
            {actionLabel}
          </button>
        ) : null}
      </div>
    </div>
  )
}
