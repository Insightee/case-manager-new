import { Link } from 'react-router-dom'

const ICONS = {
  evidence: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M8 6h8M8 10h8M8 14h5M6 4h12a2 2 0 0 1 2 2v14l-4-2-4 2-4-2-4 2V6a2 2 0 0 1 2-2z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  goals: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 4v16M4 4h12l-2 4 2 4H4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  reports: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M9 12h6M9 16h6M9 8h6M6 3h9l3 3v15H6V3z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  documentation: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3l7 3v6c0 4.4-3 8.5-7 9-4-0.5-7-4.6-7-9V6l7-3z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.5 12.5l1.8 1.8 3.7-3.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
}

function formatValue(value) {
  if (value == null || value === '') return '—'
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value).padStart(2, '0')
  }
  return String(value)
}

/**
 * Calm summary metric — Stitch row layout. Optional onClick or href for navigation.
 */
export function ClinicalMetricCard({
  value,
  count,
  label,
  icon,
  valueTone,
  tone,
  accent,
  onClick,
  href,
}) {
  const resolvedValue = value ?? count ?? 0
  const resolvedValueTone = valueTone ?? (
    tone === 'danger' ? 'attention'
      : tone === 'success' || accent === 'green' ? 'success'
        : tone === 'warning' || accent === 'amber' || accent === 'red' ? 'attention'
          : 'default'
  )
  const iconNode = icon && ICONS[icon] ? ICONS[icon] : null
  const isNumeric = typeof resolvedValue === 'number' && Number.isFinite(resolvedValue)
  const interactive = Boolean(onClick || href)
  const className = [
    'clinical-metric-card',
    'clinical-metric-card--row',
    interactive ? 'clinical-metric-card--interactive' : '',
  ].filter(Boolean).join(' ')

  const body = (
    <>
      <div className="clinical-metric-card__content">
        <span className="clinical-metric-card__label">{label}</span>
        <span
          className={[
            'clinical-metric-card__value',
            isNumeric ? 'clinical-metric-card__value--numeric' : 'clinical-metric-card__value--text',
            resolvedValueTone !== 'default' ? `clinical-metric-card__value--${resolvedValueTone}` : '',
          ].filter(Boolean).join(' ')}
        >
          {formatValue(resolvedValue)}
        </span>
      </div>
      {iconNode ? (
        <span className={`clinical-metric-card__icon-box clinical-metric-card__icon-box--${icon}`} aria-hidden="true">
          {iconNode}
        </span>
      ) : icon ? (
        <span className="clinical-metric-card__icon-box clinical-metric-card__icon-box--legacy" aria-hidden="true">
          {icon}
        </span>
      ) : null}
    </>
  )

  if (onClick) {
    return (
      <button type="button" className={className} onClick={onClick} aria-label={`${label}: ${formatValue(resolvedValue)}`}>
        {body}
      </button>
    )
  }

  if (href) {
    return (
      <Link to={href} className={className} aria-label={`${label}: ${formatValue(resolvedValue)}`}>
        {body}
      </Link>
    )
  }

  return <div className={className}>{body}</div>
}
