import { useMemo } from 'react'
import { GoalProgressCard } from './GoalProgressCard.jsx'
import { sortGoalsByAttentionNeeded } from '../../../lib/caseInsightsCompose.js'

export function IepGoalProgressSection({ goals, insightsById, selectedIds, onToggleSelect, onViewFullIep, onViewEvidence }) {
  const orderedGoals = useMemo(() => sortGoalsByAttentionNeeded(goals || []), [goals])

  const insightsByLinkedStrategyId = useMemo(() => {
    const map = new Map()
    insightsById?.forEach((item) => {
      if (item.type === 'strategy_response' && item.linkedStrategyId) map.set(item.linkedStrategyId, item)
    })
    return map
  }, [insightsById])

  if (!orderedGoals.length) {
    return (
      <section className="ci-section" aria-label="IEP goal progress">
        <div className="ci-section__head">
          <h3 className="ci-section__title">IEP Goal Progress</h3>
        </div>
        <p className="ci-empty-note">No active IEP goals yet for this case.</p>
      </section>
    )
  }

  return (
    <section className="ci-section" aria-label="IEP goal progress">
      <div className="ci-section__head">
        <h3 className="ci-section__title">IEP Goal Progress</h3>
        {onViewFullIep ? (
          <button type="button" className="ci-text-action" onClick={onViewFullIep}>
            <span className="material-symbols-outlined ci-text-action__icon" aria-hidden="true">
              list_alt
            </span>
            View Full IEP
          </button>
        ) : null}
      </div>
      <div className="ci-goal-list">
        {orderedGoals.map((goal) => (
          <GoalProgressCard
            key={goal.goalId}
            goal={goal}
            insight={insightsById?.get(`${goal.goalId}_progress`)}
            selected={selectedIds?.has(`${goal.goalId}_progress`)}
            onToggleSelect={onToggleSelect}
            insightsByLinkedStrategyId={insightsByLinkedStrategyId}
            selectedIds={selectedIds}
            onViewEvidence={onViewEvidence}
          />
        ))}
      </div>
    </section>
  )
}
