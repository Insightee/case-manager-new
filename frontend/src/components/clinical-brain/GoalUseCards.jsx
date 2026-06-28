import { GOAL_USE_OPTIONS } from '../../lib/clinicalEvidenceFields.js'
import { GOAL_USE_LABELS } from '../../lib/clinicalBrainCopy.js'

export function GoalUseCards({ value, onChange, disabled }) {
  return (
    <div className="cb-goal-use-cards" role="radiogroup" aria-label="Goal use">
      {GOAL_USE_OPTIONS.map((opt) => (
        <button
          key={opt.id}
          type="button"
          role="radio"
          aria-checked={value === opt.id}
          disabled={disabled}
          className={`cb-goal-use-card${value === opt.id ? ' is-selected' : ''}`}
          onClick={() => onChange(opt.id)}
        >
          {GOAL_USE_LABELS[opt.id] || opt.label}
        </button>
      ))}
    </div>
  )
}
