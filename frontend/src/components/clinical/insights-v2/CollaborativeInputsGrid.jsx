import { InsightSelectCheckbox } from './InsightSelectCheckbox.jsx'
import { formatInsightDate } from '../../../lib/caseInsightsCompose.js'

const SOURCE_ACCENT = {
  Parent: 'ci-input-card--parent',
  'Case Manager': 'ci-input-card--cm',
  School: 'ci-input-card--school',
}

export function CollaborativeInputsGrid({ cards, insightsById, selectedIds, onToggleSelect, onMarkIncorporated }) {
  if (!cards?.length) {
    return (
      <section className="ci-section" aria-label="Collaborative inputs">
        <h3 className="ci-section__title">Collaborative Inputs</h3>
        <p className="ci-empty-note">No parent, case manager, or school inputs logged yet.</p>
      </section>
    )
  }

  return (
    <section className="ci-section" aria-label="Collaborative inputs">
      <h3 className="ci-section__title">Collaborative Inputs</h3>
      <div className="ci-input-grid">
        {cards.map((card) => {
          const insight = insightsById?.get(card.id)
          const dateLabel = formatInsightDate(card.date)
          return (
            <div key={card.id} className={`ci-input-card ${SOURCE_ACCENT[card.source] || ''}`.trim()}>
              <div className="ci-input-card__head">
                <span className="ci-input-card__source">{card.source} input</span>
                {dateLabel ? <span className="ci-input-card__date">{dateLabel}</span> : null}
              </div>
              <p className="ci-input-card__text">{card.input}</p>
              <div className="ci-input-card__footer">
                {insight?.id ? (
                  <InsightSelectCheckbox
                    insightId={insight.id}
                    checked={selectedIds?.has(insight.id)}
                    onToggle={onToggleSelect}
                    label={`Select ${card.source} input for report`}
                  />
                ) : null}
                {card.actionStatus === 'not_incorporated' ? (
                  <button type="button" className="ci-text-action ci-text-action--small" onClick={() => onMarkIncorporated?.(card)}>
                    Mark incorporated
                  </button>
                ) : (
                  <span className="ci-input-card__incorporated">Incorporated</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
