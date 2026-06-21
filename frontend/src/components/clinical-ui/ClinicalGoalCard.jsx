import { useState } from 'react'
import { ClinicalStatusBadge } from './ClinicalStatusBadge.jsx'

const STRENGTH_LABELS = {
  weak:               'Weak operational evidence',
  moderate:           'Moderate operational evidence',
  strong_operational: 'Strong operational evidence',
}

/**
 * Goal card with expand/collapse.
 * goal: { number, title, primaryObjective, statement, evidenceStrength, status, strategies, sessionsCount, domainKey }
 * children: optional expanded body content
 */
export function ClinicalGoalCard({ goal, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)

  const dotCls = goal.evidenceStrength === 'strong_operational'
    ? 'clinical-goal-card__evidence-dot--strong'
    : goal.evidenceStrength === 'moderate'
    ? 'clinical-goal-card__evidence-dot--moderate'
    : 'clinical-goal-card__evidence-dot--weak'

  return (
    <div className="clinical-goal-card">
      <button
        type="button"
        className="clinical-goal-card__header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="clinical-goal-card__number">{goal.number || '?'}</span>
        <span style={{ flex: 1 }}>
          <p className="clinical-goal-card__title">{goal.title}</p>
          {goal.primaryObjective ? (
            <p className="clinical-goal-card__subtitle">Objective: {goal.primaryObjective}</p>
          ) : null}
        </span>
        {goal.status ? <ClinicalStatusBadge status={goal.status} /> : null}
        <span className={`clinical-goal-card__chevron${open ? ' is-open' : ''}`} aria-hidden="true">
          ▾
        </span>
      </button>

      {open ? (
        <div className="clinical-goal-card__body">
          {goal.statement ? (
            <p style={{ fontSize: '0.875rem', color: '#334155', margin: 0, fontStyle: 'italic' }}>
              "{goal.statement}"
            </p>
          ) : null}

          {goal.evidenceStrength ? (
            <div className="clinical-goal-card__evidence-bar">
              <span className={`clinical-goal-card__evidence-dot ${dotCls}`} />
              {STRENGTH_LABELS[goal.evidenceStrength] || goal.evidenceStrength}
              {goal.sessionsCount != null ? ` · ${goal.sessionsCount} sessions` : null}
            </div>
          ) : null}

          {children}
        </div>
      ) : null}
    </div>
  )
}
