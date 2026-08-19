const TONE_DOT = {
  draft: '#eab308',
  underReview: '#2563eb',
  published: '#416656',
  overdue: '#ba1a1a',
  default: '#737875',
}

export function ReportsMetricCard({ label, value, tone = 'default', active = false, onClick }) {
  const Tag = onClick ? 'button' : 'div'
  const display = String(value ?? 0).padStart(2, '0')
  return (
    <Tag
      type={onClick ? 'button' : undefined}
      className={`reports-metric-card${active ? ' is-active' : ''}`}
      onClick={onClick}
    >
      <span
        className="reports-metric-card__dot"
        style={{ background: TONE_DOT[tone] || TONE_DOT.default }}
        aria-hidden="true"
      />
      <span className="reports-metric-card__value">{display}</span>
      <span className="reports-metric-card__label">{label}</span>
    </Tag>
  )
}

export function ReportsMetricGrid({ children, className = '' }) {
  return (
    <div className={`reports-metric-grid ${className}`.trim()} role="group">
      {children}
    </div>
  )
}
