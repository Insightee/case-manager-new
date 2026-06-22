import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

const REVIEW_ACTIONS = [
  { id: 'approve_case', label: 'Approve for case' },
  { id: 'approve_pool', label: 'Approve to pool' },
  { id: 'request_edits', label: 'Request edits' },
  { id: 'reject', label: 'Reject' },
]

export function StrategyCandidateReviewPanel({ caseId, pending = [], onUpdated }) {
  const [busyId, setBusyId] = useState(null)
  const [msg, setMsg] = useState('')

  async function review(itemId, action) {
    setBusyId(itemId)
    setMsg('')
    try {
      await apiFetch(`/api/v1/cases/${caseId}/strategy-repository/${itemId}/review`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      })
      onUpdated?.()
    } catch (err) {
      setMsg(err.message || 'Review action failed')
    } finally {
      setBusyId(null)
    }
  }

  if (!pending.length) {
    return (
      <section className="cp-quality-card">
        <h3>Strategy candidates</h3>
        <p className="cp-quality-card__hint">No pending strategy candidates.</p>
      </section>
    )
  }

  return (
    <section className="cp-quality-card" aria-labelledby="strategy-review-title">
      <h3 id="strategy-review-title">Strategy candidates awaiting review</h3>
      <ul className="cp-quality-card__list">
        {pending.map((s) => (
          <li key={s.id} style={{ display: 'grid', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <div>
              <strong>{s.label}</strong>
              <span className="cp-quality-pill cp-quality-pill--draft">{s.status}</span>
            </div>
            {s.when_to_use ? <p className="cp-quality-card__hint">{s.when_to_use}</p> : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
              {REVIEW_ACTIONS.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  className="ic-btn ic-btn--ghost ic-btn--sm"
                  disabled={busyId === s.id}
                  onClick={() => review(s.id, a.id)}
                >
                  {a.label}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      {msg ? <p className="cp-quality-card__hint">{msg}</p> : null}
    </section>
  )
}
