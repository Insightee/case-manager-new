import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { coreDomainLabel } from '../../lib/coreClinicalTaxonomy.js'
import '../../styles/goals-strategies-engine.css'

async function reviewItem(caseId, kind, itemId, action, note = '') {
  const path =
    kind === 'goal'
      ? `/api/v1/cases/${caseId}/goal-repository/${itemId}/review`
      : `/api/v1/cases/${caseId}/strategy-repository/${itemId}/review`
  return apiFetch(path, {
    method: 'POST',
    body: JSON.stringify({ action, note }),
  })
}

export function AdminGoalStrategyRepositoryPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState('')
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch('/api/v1/admin/goal-strategy-repository')
      setData(res)
    } catch (err) {
      setError(err.message || 'Could not load repository')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function act(caseId, kind, itemId, action) {
    if (!caseId) return
    setBusyId(`${kind}-${itemId}-${action}`)
    setMsg('')
    try {
      await reviewItem(caseId, kind, itemId, action)
      setMsg(`Marked ${action.replace('_', ' ')}.`)
      await load()
    } catch (err) {
      setMsg(err.message || 'Review action failed')
    } finally {
      setBusyId('')
    }
  }

  if (loading) return <p className="gs-muted">Loading goal &amp; strategy repository…</p>
  if (error) return <p className="gs-error">{error}</p>

  const pendingGoals = data?.pending_goals || []
  const pendingStrategies = data?.pending_strategies || []

  return (
    <div className="gs-engine gs-engine-page">
      <header className="gs-engine-page__head">
        <div>
          <h1 className="gs-engine-page__title">Goal &amp; Strategy Repository</h1>
          <p className="gs-engine-page__sub">Review therapist-created items across cases and org pool.</p>
        </div>
      </header>

      {msg ? <p className="gs-hint">{msg}</p> : null}

      <section>
        <h2 className="sl-v2-section-label">Pending goals ({pendingGoals.length})</h2>
        <div className="gs-repo-table-wrap">
          <table className="gs-repo-table">
            <thead>
              <tr>
                <th>Goal</th>
                <th>Case</th>
                <th>Creator</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pendingGoals.map((g) => (
                <tr key={g.id}>
                  <td>
                    <strong>{g.label}</strong>
                    {(g.core_domains || []).map((d) => (
                      <span key={d} className="gs-engine-badge gs-engine-badge--active" style={{ marginLeft: 4 }}>
                        {coreDomainLabel(d, { short: true })}
                      </span>
                    ))}
                  </td>
                  <td>
                    {g.case_code ? `#${g.case_code}` : '—'}
                    {g.child_name ? ` · ${g.child_name}` : ''}
                  </td>
                  <td>{g.created_by_name || '—'}</td>
                  <td>
                    <div className="gs-repo-actions">
                      {['approve_case', 'approve_pool', 'request_edits', 'reject'].map((action) => (
                        <button
                          key={action}
                          type="button"
                          className="gs-btn"
                          disabled={busyId === `goal-${g.id}-${action}` || !g.case_id}
                          onClick={() => act(g.case_id, 'goal', g.id, action)}
                        >
                          {action.replace('_', ' ')}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
              {!pendingGoals.length ? (
                <tr>
                  <td colSpan={4} className="gs-muted">
                    No pending goals.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="sl-v2-section-label">Pending strategies ({pendingStrategies.length})</h2>
        <div className="gs-repo-table-wrap">
          <table className="gs-repo-table">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Case</th>
                <th>Creator</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pendingStrategies.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>{s.label}</strong>
                  </td>
                  <td>
                    {s.case_code ? `#${s.case_code}` : '—'}
                    {s.child_name ? ` · ${s.child_name}` : ''}
                  </td>
                  <td>{s.created_by_name || '—'}</td>
                  <td>
                    <div className="gs-repo-actions">
                      {['approve_case', 'approve_pool', 'request_edits', 'reject'].map((action) => (
                        <button
                          key={action}
                          type="button"
                          className="gs-btn"
                          disabled={busyId === `strategy-${s.id}-${action}` || !s.case_id}
                          onClick={() => act(s.case_id, 'strategy', s.id, action)}
                        >
                          {action.replace('_', ' ')}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
              {!pendingStrategies.length ? (
                <tr>
                  <td colSpan={4} className="gs-muted">
                    No pending strategies.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
