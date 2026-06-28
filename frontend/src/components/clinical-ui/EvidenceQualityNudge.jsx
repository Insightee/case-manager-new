/** Non-blocking evidence quality nudges — connection before correction */

const MESSAGES = {
  child_response: 'This evidence is stronger with a child response selected.',
  next_step: 'What should we try next? Add a next step when you can.',
  strategy_without_response:
    'You marked this strategy — what was the child\'s response?',
  strategy_helpful_no_context:
    'Strategy marked helpful. What helped: preparation, choice, environment, or adult support?',
  goal_without_strategy: 'Goal addressed — which strategy or support was used?',
}

export function EvidenceQualityNudge({ gap, onAction, actionLabel = 'Add now' }) {
  if (!gap) return null
  const message = MESSAGES[gap] || gap
  return (
    <p className="evidence-quality-nudge" role="status">
      <span>{message}</span>
      {onAction ? (
        <button type="button" className="evidence-quality-nudge__action" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </p>
  )
}

export function collectGoalEvidenceGaps(goal) {
  const gaps = []
  const ext = goal?.clinical_extension || {}
  const primary = (goal?.strategies || [])[0]
  const hasWork =
    (primary?.strategy_label || '').trim() ||
    primary?.strategy_feedback ||
    goal.participation_quality ||
    goal.clinical_extension?.child_response

  if (!hasWork) return gaps

  if ((primary?.strategy_label || '').trim() && !ext.child_response) {
    gaps.push('child_response')
  }
  if (hasWork && !ext.therapist_interpretation) {
    gaps.push('next_step')
  }
  if (primary?.strategy_feedback === 'HELPFUL' && !goal.activity_used && !(primary?.activity_used)) {
    gaps.push('strategy_helpful_no_context')
  }
  if ((goal.goal_label || '').trim() && !(primary?.strategy_label || '').trim()) {
    gaps.push('goal_without_strategy')
  }
  return gaps
}
