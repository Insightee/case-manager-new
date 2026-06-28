import { STRATEGY_FEEDBACK_OPTIONS, NEGATIVE_STRATEGY_FEEDBACK } from '../../../lib/clinicalScoring.js'

const FEEDBACK_CLASS = {
  HELPFUL: 'is-active--helpful',
  PARTLY_HELPFUL: 'is-active--partly',
  NOT_HELPFUL: 'is-active--negative',
  CHILD_REJECTED: 'is-active--negative',
  NEEDS_ADAPTATION: 'is-active--adapt',
}

export function SessionLogStrategyRow({ strategy, onChange, onRemove, readOnly }) {
  return (
    <div className="sl-strategy-row">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
        <p className="sl-strategy-row__title">{strategy.strategy_label}</p>
        {!readOnly && onRemove ? (
          <button type="button" className="ic-btn ic-btn--ghost ic-btn--sm" onClick={onRemove} aria-label="Remove strategy">
            Remove
          </button>
        ) : null}
      </div>
      <div className="sl-strategy-feedback" role="group" aria-label="Strategy feedback">
        {STRATEGY_FEEDBACK_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            disabled={readOnly}
            className={`sl-strategy-feedback__btn${
              strategy.strategy_feedback === opt.id ? ` ${FEEDBACK_CLASS[opt.id] || ''}` : ''
            }`}
            aria-pressed={strategy.strategy_feedback === opt.id}
            onClick={() =>
              onChange({ strategy_feedback: strategy.strategy_feedback === opt.id ? null : opt.id })
            }
          >
            {opt.label}
          </button>
        ))}
      </div>
      <label className="ic-session-log-field" style={{ margin: 0 }}>
        <span className="ic-session-log-field__hint">Optional note</span>
        <input
          type="text"
          value={strategy.short_note || ''}
          disabled={readOnly}
          placeholder="What happened with this strategy?"
          onChange={(e) => onChange({ short_note: e.target.value })}
        />
      </label>
    </div>
  )
}

export function strategyNeedsAlternatives(strategy) {
  return strategy?.strategy_feedback && NEGATIVE_STRATEGY_FEEDBACK.has(strategy.strategy_feedback)
}
