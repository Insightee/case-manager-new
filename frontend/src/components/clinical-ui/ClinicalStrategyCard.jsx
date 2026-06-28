/**
 * Strategy card for IEP and strategy pool displays.
 * strategy: { title, category, description, purpose, howToUse, whenToUse, usageCount, status }
 * onRemove: optional — only shown if provided (for IEP-linked strategies)
 */
export function ClinicalStrategyCard({ strategy, onRemove }) {
  return (
    <div className="clinical-strategy-card">
      <div className="clinical-strategy-card__header">
        <p className="clinical-strategy-card__title">{strategy.title}</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', flexShrink: 0 }}>
          {strategy.category ? (
            <span className="clinical-strategy-card__category">{strategy.category}</span>
          ) : null}
          {onRemove ? (
            <button
              type="button"
              onClick={() => onRemove(strategy)}
              aria-label={`Remove ${strategy.title}`}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#94a3b8',
                fontSize: '1rem',
                padding: '2px',
              }}
            >
              ✕
            </button>
          ) : null}
        </div>
      </div>

      {strategy.description ? (
        <p className="clinical-strategy-card__desc">{strategy.description}</p>
      ) : null}

      <dl className="clinical-strategy-card__meta-grid">
        {strategy.purpose ? (
          <div className="clinical-strategy-card__meta-item">
            <dt>Purpose</dt>
            <dd>{strategy.purpose}</dd>
          </div>
        ) : null}
        {strategy.howToUse ? (
          <div className="clinical-strategy-card__meta-item">
            <dt>How to use</dt>
            <dd>{strategy.howToUse}</dd>
          </div>
        ) : null}
        {strategy.whenToUse ? (
          <div className="clinical-strategy-card__meta-item">
            <dt>When to use</dt>
            <dd>{strategy.whenToUse}</dd>
          </div>
        ) : null}
        {strategy.usageCount != null ? (
          <div className="clinical-strategy-card__meta-item">
            <dt>Used</dt>
            <dd>{strategy.usageCount} sessions</dd>
          </div>
        ) : null}
      </dl>
    </div>
  )
}
