import { useMemo } from 'react'
import { NEUROAFFIRMATIVE_PREFER, scanNeuroaffirmative } from '../../lib/clinicalDomains.js'

export function NeuroaffirmativeFieldHint({ value, showTips = true }) {
  const flagged = useMemo(() => scanNeuroaffirmative(value), [value])

  if (!showTips && flagged.length === 0) return null

  return (
    <div className="cp-hint" style={{ marginTop: 8 }}>
      {flagged.length > 0 ? (
        <p className="cp-hint--warn" role="status">
          Consider reframing: found phrasing that may pathologise ({flagged.join(', ')}). Prefer
          strengths-based language.
        </p>
      ) : null}
      {showTips ? (
        <details style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 6 }}>
          <summary>Neuroaffirmative language tips</summary>
          <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.1rem' }}>
            {NEUROAFFIRMATIVE_PREFER.slice(0, 6).map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}
