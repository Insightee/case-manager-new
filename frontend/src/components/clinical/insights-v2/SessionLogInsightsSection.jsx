import { InsightSelectCheckbox } from './InsightSelectCheckbox.jsx'

const CARD_DEFS = [
  { key: 'helping', title: "What's helping", icon: 'thumb_up', tone: 'ci-evidence-card--positive' },
  { key: 'needsAdapting', title: 'What needs adapting', icon: 'sync_alt', tone: 'ci-evidence-card--attention' },
  { key: 'supportConcerns', title: 'Support needs / concerns', icon: 'shield', tone: 'ci-evidence-card--muted' },
]

export function SessionLogInsightsSection({ evidence, insightsById, selectedIds, onToggleSelect }) {
  if (!evidence) return null

  return (
    <section className="ci-section" aria-label="Session log insights and evidence">
      <h3 className="ci-section__title">Session Log Insights &amp; Evidence</h3>
      <div className="ci-evidence-grid">
        {CARD_DEFS.map(({ key, title, icon, tone }) => {
          const card = evidence[key]
          if (!card) return null
          const insight = insightsById?.get(card.id)
          return (
            <div key={key} className={`ci-evidence-card ${tone}`}>
              <div className="ci-evidence-card__head">
                <span className="material-symbols-outlined" aria-hidden="true">
                  {icon}
                </span>
                <h4 className="ci-evidence-card__title">{title}</h4>
              </div>
              <p className="ci-evidence-card__text">&ldquo;{card.summary}&rdquo;</p>
              <div className="ci-evidence-card__footer">
                <p className="ci-source-line">{card.sourceLine}</p>
                {insight?.id ? (
                  <InsightSelectCheckbox
                    insightId={insight.id}
                    checked={selectedIds?.has(insight.id)}
                    onToggle={onToggleSelect}
                    label={`Select "${title}" for report`}
                  />
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
