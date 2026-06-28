import { SESSION_LOG_SCORES } from '../../../lib/clinicalScoring.js'
import { ScoreHelpButton } from './ScoreHelpButton.jsx'

function anchorHelpBody(anchors) {
  return (
    <ul className="sl-score-help__list">
      {[0, 1, 2, 3, 4].map((n) => (
        <li key={n}>
          <strong>{n}</strong> — {anchors[n]}
        </li>
      ))}
    </ul>
  )
}

export function SessionLogScoreScale({ dimension, value, onChange, disabled, compact = false }) {
  const dim = SESSION_LOG_SCORES.find((d) => d.key === dimension) || SESSION_LOG_SCORES[0]
  return (
    <div className="sl-score-block">
      <div className="sl-score-block__head">
        <p className="sl-score-block__label">{dim.label}</p>
        <ScoreHelpButton title={dim.label} body={anchorHelpBody(dim.anchors)} compact />
      </div>
      <div className="sl-score-scale" role="group" aria-label={dim.label}>
        {[0, 1, 2, 3, 4].map((n) => (
          <button
            key={n}
            type="button"
            className={`sl-score-scale__btn${value === n ? ' is-active' : ''}`}
            aria-pressed={value === n}
            disabled={disabled}
            title={dim.anchors[n]}
            onClick={() => onChange(value === n ? null : n)}
          >
            {n}
          </button>
        ))}
      </div>
      {!compact && value != null ? (
        <p className="sl-score-block__anchor">{dim.anchors[value]}</p>
      ) : null}
    </div>
  )
}
