import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { domainLabel } from '../../../lib/clinicalDomains.js'

const REVIEW_ACTIONS = [
  { id: 'approve_case', label: 'Approve for case' },
  { id: 'approve_pool', label: 'Approve to pool' },
  { id: 'request_edits', label: 'Request edits' },
  { id: 'reject', label: 'Reject' },
]

export function GoalQualityReviewPanel({ caseId, pending = [], onUpdated }) {
  const [busyId, setBusyId] = useState(null)
  const [msg, setMsg] = useState('')

  async function review(itemId, action) {
    setBusyId(itemId)
    setMsg('')
    try {
      await apiFetch(`/api/v1/cases/${caseId}/goal-repository/${itemId}/review`, {
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
        <h3>Goal candidates</h3>
        <p className="cp-quality-card__hint">No pending goal candidates.</p>
      </section>
    )
  }

  return (
    <section className="cp-quality-card" aria-labelledby="goal-review-title">
      <h3 id="goal-review-title">Goal candidates awaiting review</h3>
      <ul className="cp-quality-card__list">
        {pending.map((g) => (
          <li key={g.id} style={{ display: 'grid', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <div>
              <strong>{g.label}</strong>
              {g.domain_key ? (
                <span className="cp-quality-pill cp-quality-pill--draft">{domainLabel(g.domain_key)}</span>
              ) : null}
              <span className="cp-quality-pill cp-quality-pill--draft">{g.status}</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
              {REVIEW_ACTIONS.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  className="ic-btn ic-btn--ghost ic-btn--sm"
                  disabled={busyId === g.id}
                  onClick={() => review(g.id, a.id)}
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
