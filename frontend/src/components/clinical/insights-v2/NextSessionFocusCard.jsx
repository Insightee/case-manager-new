import { InsightSelectCheckbox } from './InsightSelectCheckbox.jsx'

export function NextSessionFocusCard({ focus, insight, selected, onToggleSelect }) {
  if (!focus) return null

  const slots = [
    { label: 'Priority Goal', value: focus.goalLabel },
    { label: 'Key Strategy', value: focus.strategyLabel || 'No strategy attached yet' },
    { label: 'Observe', value: focus.observe },
    { label: 'Adapt', value: focus.adapt },
  ]

  return (
    <section className="ci-card ci-next-session" aria-label="Next session focus">
      <div className="ci-card__head">
        <span className="material-symbols-outlined ci-card__icon" aria-hidden="true">
          rocket_launch
        </span>
        <h3 className="ci-card__title ci-card__title--eyebrow">Next Session Focus</h3>
        {insight?.id ? (
          <InsightSelectCheckbox
            insightId={insight.id}
            checked={selected}
            onToggle={onToggleSelect}
            label="Select next session focus for report"
          />
        ) : null}
      </div>

      <div className="ci-next-session__grid">
        {slots.map((slot) => (
          <div key={slot.label} className="ci-next-session__slot">
            <p className="ci-next-session__label">{slot.label}</p>
            <p className="ci-next-session__value">{slot.value}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
