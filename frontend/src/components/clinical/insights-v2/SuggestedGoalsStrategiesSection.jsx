import { StatusChip } from './StatusChip.jsx'

export function SuggestedGoalsStrategiesSection({ suggested, onSaveDraftGoal, onSendIepReview, onTryNextSession, onSaveCaseSpecific }) {
  const goals = suggested?.goals || []
  const strategies = suggested?.strategies || []

  if (!goals.length && !strategies.length) return null

  return (
    <section className="ci-section" aria-label="Suggested goals and strategies">
      <h3 className="ci-section__title">Suggested Goals &amp; Strategies</h3>
      <div className="ci-suggested-grid">
        <div className="ci-card ci-suggested-card">
          <div className="ci-card__head">
            <span className="material-symbols-outlined ci-card__icon" aria-hidden="true">
              flag
            </span>
            <h4 className="ci-suggested-card__title">Suggested Goals</h4>
          </div>
          {goals.length ? (
            <ul className="ci-suggested-list">
              {goals.map((goal) => (
                <li key={goal.goalId} className="ci-suggested-item">
                  <div className="ci-suggested-item__body">
                    <p className="ci-suggested-item__text">{goal.rationale || goal.label}</p>
                    <StatusChip status={goal.status} />
                  </div>
                  <p className="ci-suggested-item__note">{goal.note}</p>
                  <div className="ci-suggested-item__actions">
                    <button type="button" className="ci-text-action ci-text-action--small" onClick={() => onSaveDraftGoal?.(goal)}>
                      Save as Draft Goal
                    </button>
                    <button type="button" className="ci-text-action ci-text-action--small" onClick={() => onSendIepReview?.(goal)}>
                      Send to IEP Review
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="ci-empty-note">No suggested goals from recent activity yet.</p>
          )}
        </div>

        <div className="ci-card ci-suggested-card">
          <div className="ci-card__head">
            <span className="material-symbols-outlined ci-card__icon" aria-hidden="true">
              tips_and_updates
            </span>
            <h4 className="ci-suggested-card__title">Suggested Strategies</h4>
          </div>
          {strategies.length ? (
            <ul className="ci-suggested-list">
              {strategies.map((strategy) => (
                <li key={strategy.strategyId} className="ci-suggested-item">
                  <div className="ci-suggested-item__body">
                    <p className="ci-suggested-item__text">{strategy.howToUse || strategy.label}</p>
                    <StatusChip status={strategy.status} />
                  </div>
                  <p className="ci-suggested-item__note">{strategy.note}</p>
                  <div className="ci-suggested-item__actions">
                    <button type="button" className="ci-text-action ci-text-action--small" onClick={() => onTryNextSession?.(strategy)}>
                      Try next session
                    </button>
                    <button type="button" className="ci-text-action ci-text-action--small" onClick={() => onSaveCaseSpecific?.(strategy)}>
                      Save as case-specific
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="ci-empty-note">No suggested strategies from recent activity yet.</p>
          )}
        </div>
      </div>
    </section>
  )
}
