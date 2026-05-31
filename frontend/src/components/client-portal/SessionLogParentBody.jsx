import { useState } from 'react'
import { getParentLogSections } from '../../lib/parentSessionLogDisplay.js'

function SessionLogSections({ log, clampLines = false }) {
  const sections = getParentLogSections(log)

  if (!sections.length) {
    return (
      <p className="session-card__empty-note">
        Your therapist has not added session notes for this visit yet.
      </p>
    )
  }

  return (
    <div className={`session-card__body${clampLines ? ' session-card__body--preview' : ' session-card__body--expanded'}`}>
      {sections.map((section) => (
        <section
          key={section.key}
          className={`session-card__section session-card__section--${section.variant}`}
        >
          <h4 className="session-card__section-label">{section.label}</h4>
          {section.hint ? <p className="session-card__section-hint">{section.hint}</p> : null}
          <p
            className={`session-card__section-text${clampLines ? ' session-card__section-text--clamp' : ''}`}
          >
            {section.value}
          </p>
        </section>
      ))}
    </div>
  )
}

export function SessionLogParentBody({ log, collapsible = false }) {
  const [expanded, setExpanded] = useState(false)
  const sections = getParentLogSections(log)

  if (!collapsible) {
    return <SessionLogSections log={log} />
  }

  if (!sections.length) {
    return (
      <p className="session-card__empty-note">
        Your therapist has not added session notes for this visit yet.
      </p>
    )
  }

  if (!expanded) {
    return (
      <div className="session-card__notes">
        <button
          type="button"
          className="session-card__notes-hit"
          onClick={() => setExpanded(true)}
          aria-expanded={false}
        >
          <SessionLogSections log={log} clampLines />
          <span className="session-card__notes-toggle session-card__notes-toggle--block">
            Tap to expand session notes
          </span>
        </button>
      </div>
    )
  }

  return (
    <div className="session-card__notes">
      <SessionLogSections log={log} />
      <button
        type="button"
        className="session-card__notes-toggle"
        onClick={() => setExpanded(false)}
        aria-expanded
      >
        Show less
      </button>
    </div>
  )
}
