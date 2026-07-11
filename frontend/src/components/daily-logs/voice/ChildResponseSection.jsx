import { useState } from 'react'
import {
  CHILD_RESPONSE_SIGNALS,
  COMMON_RESPONSE_SIGNAL_IDS,
  responseSignalLabel,
  toggleResponseSignal,
} from '../../../lib/structuredSessionEvidence.js'

/**
 * How did the child respond — compact by default: inferred signals plus
 * three common options; "Add another response" reveals the full vocabulary.
 */
export function ChildResponseSection({ structuredSession, onChange }) {
  const selected = structuredSession.child_response_signals || []
  const [showAll, setShowAll] = useState(false)

  const compactIds = [...new Set([...selected, ...COMMON_RESPONSE_SIGNAL_IDS])]
  const visible = showAll
    ? CHILD_RESPONSE_SIGNALS
    : CHILD_RESPONSE_SIGNALS.filter((s) => compactIds.includes(s.id))

  return (
    <section className="vsl-stitch__card" aria-label="How did the child respond">
      <h3 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
        How did the child respond?
      </h3>
      {selected.length ? (
        <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '0 0 8px' }}>
          From your update: {selected.map(responseSignalLabel).join(' · ')}
        </p>
      ) : null}
      <div className="vsl-stitch__chip-row">
        {visible.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`vsl-stitch__chip ${selected.includes(s.id) ? 'vsl-stitch__chip--on' : ''}`}
            onClick={() => onChange(toggleResponseSignal(structuredSession, s.id))}
          >
            {s.label}
          </button>
        ))}
        {!showAll ? (
          <button type="button" className="vsl-stitch__chip" onClick={() => setShowAll(true)}>
            + Add another response
          </button>
        ) : null}
      </div>
    </section>
  )
}
