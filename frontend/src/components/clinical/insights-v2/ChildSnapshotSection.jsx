import { InsightSelectCheckbox } from './InsightSelectCheckbox.jsx'

const CARD_DEFS = [
  { key: 'strengthsInterests', icon: 'star', label: 'Strengths & Interests' },
  { key: 'helpfulSupports', icon: 'verified', label: 'Helpful Supports' },
  { key: 'supportNeeds', icon: 'info', label: 'Support Needs' },
]

export function ChildSnapshotSection({ child, insight, selected, onToggleSelect, onEditSnapshot }) {
  if (!child) return null

  return (
    <section className="ci-card ci-child-snapshot" aria-label="Child snapshot">
      <div className="ci-card__head">
        <span className="material-symbols-outlined ci-card__icon" aria-hidden="true">
          eco
        </span>
        <h3 className="ci-card__title">Child Snapshot</h3>
        {insight?.id ? (
          <InsightSelectCheckbox
            insightId={insight.id}
            checked={selected}
            onToggle={onToggleSelect}
            label="Select child snapshot for report"
          />
        ) : null}
      </div>

      <p className="ci-child-snapshot__summary">{child.summaryParagraph}</p>

      <div className="ci-child-snapshot__grid">
        {CARD_DEFS.map(({ key, icon, label }) => {
          const values = child[key] || []
          return (
            <div key={key} className="ci-mini-card">
              <div className="ci-mini-card__head">
                <span className="material-symbols-outlined ci-mini-card__icon" aria-hidden="true">
                  {icon}
                </span>
                <p className="ci-mini-card__label">{label}</p>
              </div>
              <p className="ci-mini-card__value">
                {values.length ? values.join(', ') : 'Still building evidence for this area.'}
              </p>
            </div>
          )
        })}
        <div className="ci-mini-card">
          <div className="ci-mini-card__head">
            <span className="material-symbols-outlined ci-mini-card__icon" aria-hidden="true">
              insights
            </span>
            <p className="ci-mini-card__label">Recent Pattern</p>
          </div>
          <p className="ci-mini-card__value">{child.recentPattern}</p>
        </div>
      </div>

      <div className="ci-card__footer">
        <p className="ci-source-line">{child.sourceLine}</p>
        {onEditSnapshot ? (
          <button type="button" className="ci-text-action" onClick={onEditSnapshot}>
            Edit Snapshot
          </button>
        ) : null}
      </div>
    </section>
  )
}
