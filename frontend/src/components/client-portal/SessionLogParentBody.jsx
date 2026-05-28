import { getParentLogSections } from '../../lib/parentSessionLogDisplay.js'

export function SessionLogParentBody({ log }) {
  const sections = getParentLogSections(log)

  if (!sections.length) {
    return (
      <p className="session-card__empty-note">
        Your therapist has not added session notes for this visit yet.
      </p>
    )
  }

  return (
    <div className="session-card__body">
      {sections.map((section) => (
        <section
          key={section.key}
          className={`session-card__section session-card__section--${section.variant}`}
        >
          <h4 className="session-card__section-label">{section.label}</h4>
          {section.hint ? <p className="session-card__section-hint">{section.hint}</p> : null}
          <p className="session-card__section-text">{section.value}</p>
        </section>
      ))}
    </div>
  )
}
