import { StatusChip } from './StatusChip.jsx'
import { InsightSelectCheckbox } from './InsightSelectCheckbox.jsx'
import { StrategyResponseAccordion } from './StrategyResponseAccordion.jsx'

export function GoalProgressCard({ goal, insight, selected, onToggleSelect, insightsByLinkedStrategyId, selectedIds, onViewEvidence }) {
  return (
    <article className="ci-card ci-goal-card">
      <div className="ci-goal-card__top">
        <div className="ci-goal-card__heading">
          {goal.domainKey ? <p className="ci-goal-card__eyebrow">{goal.domainKey.replace(/_/g, ' ')}</p> : null}
          <h4 className="ci-goal-card__name">{goal.label}</h4>
        </div>
        <div className="ci-goal-card__status">
          <StatusChip status={goal.status} />
          <button type="button" className="ci-text-action ci-text-action--small" onClick={() => onViewEvidence?.(goal)}>
            View evidence
          </button>
        </div>
      </div>

      <div className="ci-goal-card__body">
        <div>
          <p className="ci-goal-card__label">Measurement</p>
          <p className="ci-goal-card__measurement">{goal.measurement}</p>
        </div>
        <div>
          <p className="ci-goal-card__label">Progress insight</p>
          <p className={`ci-goal-card__insight${goal.status === 'Needs adapting' ? ' ci-goal-card__insight--attention' : ''}`}>
            {goal.progressInsight}
          </p>
        </div>
      </div>

      <StrategyResponseAccordion
        strategies={goal.strategies}
        insightsByLinkedStrategyId={insightsByLinkedStrategyId}
        selectedIds={selectedIds}
        onToggleSelect={onToggleSelect}
      />

      <div className="ci-card__footer">
        <p className="ci-source-line">{goal.evidenceSourceLine}</p>
        <div className="ci-goal-card__actions">
          {insight?.id ? (
            <InsightSelectCheckbox
              insightId={insight.id}
              checked={selected}
              onToggle={onToggleSelect}
              label={`Select ${goal.label} progress insight for report`}
            />
          ) : null}
          <span className="ci-goal-card__next-step">{goal.nextStep}</span>
        </div>
      </div>
    </article>
  )
}
