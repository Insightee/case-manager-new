import { useState } from 'react'
import { StatusChip } from './StatusChip.jsx'
import { InsightSelectCheckbox } from './InsightSelectCheckbox.jsx'

export function StrategyResponseAccordion({ strategies, insightsByLinkedStrategyId, selectedIds, onToggleSelect }) {
  const [openId, setOpenId] = useState(null)
  if (!strategies?.length) return null

  return (
    <div className="ci-strategy-accordion">
      <div className="ci-strategy-accordion__head">
        <span className="material-symbols-outlined" aria-hidden="true">
          lightbulb
        </span>
        <h5 className="ci-strategy-accordion__title">Strategy Response</h5>
      </div>

      {strategies.map((strategy) => {
        const isOpen = openId === strategy.strategyId
        const insight = insightsByLinkedStrategyId?.get(strategy.strategyId)
        return (
          <div key={strategy.strategyId} className="ci-strategy-row">
            <button
              type="button"
              className="ci-strategy-row__summary"
              onClick={() => setOpenId(isOpen ? null : strategy.strategyId)}
              aria-expanded={isOpen}
            >
              <div className="ci-strategy-row__text">
                <p className="ci-strategy-row__name">{strategy.label}</p>
                {strategy.status ? <p className="ci-strategy-row__badge-text">{strategy.status}</p> : null}
              </div>
              <div className="ci-strategy-row__meta">
                <StatusChip status={strategy.response} />
                <span className="material-symbols-outlined ci-strategy-row__chevron" aria-hidden="true">
                  {isOpen ? 'expand_less' : 'expand_more'}
                </span>
              </div>
            </button>

            {isOpen ? (
              <div className="ci-strategy-row__details">
                {strategy.whereItHelped ? (
                  <p className="ci-strategy-row__detail">
                    <strong>Where it helped:</strong> {strategy.whereItHelped}
                  </p>
                ) : null}
                {strategy.whereNeedsAdapting ? (
                  <p className="ci-strategy-row__detail">
                    <strong>Where it needs adapting:</strong> {strategy.whereNeedsAdapting}
                  </p>
                ) : null}
                <p className="ci-source-line">{strategy.evidenceSourceLine}</p>
                <div className="ci-strategy-row__actions">
                  {insight?.id ? (
                    <InsightSelectCheckbox
                      insightId={insight.id}
                      checked={selectedIds?.has(insight.id)}
                      onToggle={onToggleSelect}
                      label={`Select ${strategy.label} response for report`}
                    />
                  ) : null}
                  <span className="ci-strategy-row__action-hint">
                    {strategy.response === 'Needs adapting' ? 'Adapt' : 'Continue'}
                  </span>
                </div>
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
