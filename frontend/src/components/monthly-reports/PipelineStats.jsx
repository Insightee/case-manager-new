const CARDS = [
  { key: 'draft', label: 'Draft', tone: 'warning', icon: '🟡' },
  { key: 'underReview', label: 'Under Review', tone: 'info', icon: '🔵' },
  { key: 'published', label: 'Published', tone: 'success', icon: '🟢' },
  { key: 'overdue', label: 'Overdue', tone: 'danger', icon: '🔴' },
]

export function PipelineStats({ counts, activeFilter, onFilter }) {
  return (
    <div className="clinical-metric-grid" role="group" aria-label="Report pipeline overview">
      {CARDS.map((c) => {
        const value = counts[c.key] ?? 0
        const isActive = activeFilter === c.key
        return (
          <button
            key={c.key}
            type="button"
            onClick={() => onFilter(c.key)}
            className={`clinical-metric-card clinical-metric-card--${c.tone}`}
            style={{
              cursor: 'pointer',
              textAlign: 'left',
              outline: isActive ? '2px solid var(--clinical-primary-border)' : 'none',
              outlineOffset: 2,
            }}
          >
            {c.icon ? <span className="clinical-metric-card__icon" aria-hidden="true">{c.icon}</span> : null}
            <span className="clinical-metric-card__count">{String(value).padStart(2, '0')}</span>
            <span className="clinical-metric-card__label">{c.label}</span>
          </button>
        )
      })}
    </div>
  )
}
