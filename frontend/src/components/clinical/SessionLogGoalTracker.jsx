import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { CLINICAL_DOMAINS } from '../../lib/clinicalDomains.js'
import { NeuroaffirmativeFieldHint } from '../clinical/NeuroaffirmativeFieldHint.jsx'
import { STRUCTURED_SESSION_EVIDENCE } from '../../lib/reportsRevampFlags.js'

const SUPPORT_LEVELS = [
  { id: 'MINIMUM', label: 'Minimum' },
  { id: 'MODERATE', label: 'Moderate' },
  { id: 'MAXIMUM', label: 'Maximum' },
]

export function SessionLogGoalTracker({ logId, caseId, onSaved }) {
  const [goals, setGoals] = useState([])
  const [strategies, setStrategies] = useState([])
  const [iepGoals, setIepGoals] = useState([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    if (!STRUCTURED_SESSION_EVIDENCE || !logId) return
    setLoading(true)
    try {
      const [evidence, iepCtx] = await Promise.all([
        apiFetch(`/api/v1/daily-logs/${logId}/session-evidence`).catch(() => ({ goals: [], strategies: [] })),
        apiFetch(`/api/v1/reports/monthly/iep-context?case_id=${caseId}`).catch(() => ({ goals: [] })),
      ])
      setGoals(evidence.goals?.length ? evidence.goals : [{ goal_label: '', support_level: 'MODERATE', response_note: '' }])
      setStrategies(evidence.strategies?.length ? evidence.strategies : [])
      setIepGoals(iepCtx.goals || iepCtx.active_goals || [])
    } finally {
      setLoading(false)
    }
  }, [logId, caseId])

  useEffect(() => {
    load()
  }, [load])

  if (!STRUCTURED_SESSION_EVIDENCE) return null
  if (loading) return <p className="ic-case-panel__muted">Loading goal tracker…</p>

  function updateGoal(i, patch) {
    setGoals((prev) => prev.map((g, idx) => (idx === i ? { ...g, ...patch } : g)))
  }

  async function save() {
    setMsg('')
    try {
      await apiFetch(`/api/v1/daily-logs/${logId}/session-evidence`, {
        method: 'PUT',
        body: JSON.stringify({ goals, strategies }),
      })
      setMsg('Session evidence saved.')
      onSaved?.()
    } catch (err) {
      setMsg(err.message || 'Could not save')
    }
  }

  return (
    <div className="cp-session-goal-tracker cp-card">
      <h4>Goal & strategy evidence</h4>
      {goals.map((g, i) => (
        <div key={i} className="cp-card cp-card--nested">
          <label>
            IEP goal
            <select
              value={g.goal_card_id || ''}
              onChange={(e) => {
                const opt = iepGoals.find((x) => String(x.id) === e.target.value)
                updateGoal(i, {
                  goal_card_id: opt?.id || null,
                  goal_label: opt?.label || g.goal_label,
                  domain_key: opt?.domain_key,
                })
              }}
            >
              <option value="">Custom / typed</option>
              {iepGoals.map((og) => (
                <option key={og.id} value={og.id}>{og.label || og.goal_statement}</option>
              ))}
            </select>
          </label>
          <label>
            Goal note
            <textarea value={g.goal_label || ''} onChange={(e) => updateGoal(i, { goal_label: e.target.value })} rows={2} />
            <NeuroaffirmativeFieldHint text={g.goal_label} />
          </label>
          <div className="cp-support-pills">
            {SUPPORT_LEVELS.map((lvl) => (
              <button
                key={lvl.id}
                type="button"
                className={`cp-support-pill${g.support_level === lvl.id ? ' is-active' : ''}`}
                onClick={() => updateGoal(i, { support_level: lvl.id })}
              >
                {lvl.label}
              </button>
            ))}
          </div>
          <label>
            Response note
            <textarea value={g.response_note || ''} onChange={(e) => updateGoal(i, { response_note: e.target.value })} rows={2} />
          </label>
        </div>
      ))}
      <button type="button" className="ic-btn ic-btn--ghost" onClick={() => setGoals((p) => [...p, { goal_label: '', support_level: 'MODERATE' }])}>
        Add goal entry
      </button>
      {msg ? <p className="ic-case-panel__hint">{msg}</p> : null}
      <button type="button" className="ic-btn ic-btn--primary" onClick={save}>Save evidence</button>
      <p className="ic-case-panel__muted">Domains: {CLINICAL_DOMAINS.slice(0, 3).map((d) => d.label).join(', ')}…</p>
    </div>
  )
}
