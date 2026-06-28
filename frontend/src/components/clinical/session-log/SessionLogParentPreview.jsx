import { TaxonomyTicker } from '../ClinicalTaxonomyPicker.jsx'
import { STRATEGY_FEEDBACK_OPTIONS, goalHasSessionWork } from '../../../lib/clinicalScoring.js'

const FEEDBACK_LABELS = Object.fromEntries(STRATEGY_FEEDBACK_OPTIONS.map((o) => [o.id, o.label]))

/** Read-only preview of what parents / clients see from session evidence + summary. */
export function SessionLogParentPreview({ sessionEvidence, parentNotes = '' }) {
  const goals = (sessionEvidence?.goals || []).filter(goalHasSessionWork)
  const hasGoals = goals.length > 0

  if (!hasGoals && !parentNotes?.trim()) {
    return (
      <details className="sl-parent-preview">
        <summary className="sl-parent-preview__summary">Preview: what family will see</summary>
        <p className="gs-muted">Add goals and a parent summary to preview the family view.</p>
      </details>
    )
  }

  return (
    <details className="sl-parent-preview">
      <summary className="sl-parent-preview__summary">Preview: what family will see</summary>
      <div className="sl-parent-preview__body">
        {goals.map((goal, i) => {
          const primary = goal.strategies?.[0]
          if (!(goal.goal_label || '').trim()) return null
          return (
            <article key={i} className="sl-parent-preview__goal">
              <TaxonomyTicker domains={goal.core_domains} environments={goal.core_environments} />
              <h4 className="sl-parent-preview__goal-title">{goal.goal_label}</h4>
              {goal.goal_description ? (
                <p className="sl-parent-preview__goal-brief">{goal.goal_description}</p>
              ) : null}
              {primary?.strategy_label ? (
                <p className="sl-parent-preview__strategy">
                  <strong>Strategy used:</strong> {primary.strategy_label}
                </p>
              ) : null}
              {primary?.short_note ? (
                <p className="sl-parent-preview__note">{primary.short_note}</p>
              ) : null}
              {primary?.strategy_feedback ? (
                <p className="sl-parent-preview__feedback">
                  Session feedback: {FEEDBACK_LABELS[primary.strategy_feedback] || primary.strategy_feedback}
                </p>
              ) : null}
            </article>
          )
        })}
        {parentNotes?.trim() ? (
          <section className="sl-parent-preview__summary-block">
            <h4 className="sl-parent-preview__summary-title">Session summary</h4>
            <p>{parentNotes.trim()}</p>
          </section>
        ) : null}
      </div>
    </details>
  )
}
