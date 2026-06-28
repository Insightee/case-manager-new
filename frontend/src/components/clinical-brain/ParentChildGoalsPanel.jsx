import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { PARENT_GOALS_INTRO } from '../../lib/clinicalBrainCopy.js'
import '../../styles/clinical-brain.css'

const INPUT_CHIPS = [
  { id: 'see_at_home', label: 'I see this at home' },
  { id: 'hard_at_home', label: 'This is hard at home' },
  { id: 'strategy_helps', label: 'This strategy helps' },
  { id: 'strategy_not_fit', label: 'This strategy does not fit' },
  { id: 'team_consider', label: 'I want the team to consider' },
]

/**
 * Parent-safe goals — collaborative, no internal clinical fields.
 */
export function ParentChildGoalsPanel({ caseId, goals }) {
  const controlled = goals?.length ? goals : null
  const [fetched, setFetched] = useState([])
  const [loading, setLoading] = useState(Boolean(caseId && !controlled))
  const [error, setError] = useState('')
  const [activeGoal, setActiveGoal] = useState(null)
  const [inputType, setInputType] = useState('see_at_home')
  const [comment, setComment] = useState('')
  const [submitMsg, setSubmitMsg] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    if (!caseId || controlled) return
    setLoading(true)
    setError('')
    try {
      const res = await apiFetch(`/api/v1/parent/cases/${caseId}/parent-safe-goals`)
      setFetched(res.items || [])
    } catch (err) {
      setError(err.message || 'Could not load shared goals')
      setFetched([])
    } finally {
      setLoading(false)
    }
  }, [caseId, controlled])

  useEffect(() => {
    load()
  }, [load])

  const items = controlled || fetched

  async function submitInput(goal) {
    if (!caseId || !goal?.id) return
    setSubmitting(true)
    setSubmitMsg('')
    try {
      await apiFetch(`/api/v1/parent/cases/${caseId}/goal-inputs`, {
        method: 'POST',
        body: JSON.stringify({
          goal_ref: String(goal.id),
          input_type: inputType,
          comment: comment.trim() || null,
        }),
      })
      setSubmitMsg('Thank you — the clinical team will review suggestions before updating goals.')
      setComment('')
      setActiveGoal(null)
    } catch (err) {
      setSubmitMsg(err.message || 'Could not send input right now.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p className="gs-muted">Loading shared goals…</p>

  return (
    <div className="cb-parent-goals">
      <p className="gs-muted mb-4">{PARENT_GOALS_INTRO}</p>
      <p className="gs-muted text-sm mb-4">
        Your input helps the team understand how support is working across home, school, and daily routines.
        The clinical team will review suggestions before updating goals.
      </p>
      {error ? <p className="gs-error">{error}</p> : null}
      {submitMsg ? <p className="gs-muted mb-3">{submitMsg}</p> : null}

      <div className="cb-parent-goals__grid">
        {items.map((g) => (
          <article key={g.id} className="cb-parent-goal cb-parent-goal--bento">
            <p className="cb-parent-goal__eyebrow">We are supporting</p>
            <h3>{g.goal_title_parent || g.focus_area || g.label}</h3>

            {g.everyday_participation_reason || g.parent_friendly_description ? (
              <div className="mt-3">
                <p className="cb-parent-goal__label">Why this matters</p>
                <p>{g.everyday_participation_reason || g.parent_friendly_description}</p>
              </div>
            ) : null}

            {g.current_supports || g.what_helps ? (
              <div className="mt-3">
                <p className="cb-parent-goal__label">What helps</p>
                <p>{g.current_supports || g.what_helps}</p>
              </div>
            ) : null}

            {g.progress_signals_parent_safe?.length ? (
              <div className="mt-3">
                <p className="cb-parent-goal__label">What we are noticing</p>
                <ul>
                  {g.progress_signals_parent_safe.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </div>
            ) : g.what_we_notice ? (
              <div className="mt-3">
                <p className="cb-parent-goal__label">What we are noticing</p>
                <p>{g.what_we_notice}</p>
              </div>
            ) : null}

            {g.next_focus ? (
              <div className="mt-3">
                <p className="cb-parent-goal__label">Next focus</p>
                <p>{g.next_focus}</p>
              </div>
            ) : null}

            {g.show_parent_comment_box !== false ? (
              <div className="mt-4">
                <p className="cb-parent-goal__label">Share your input</p>
                {activeGoal === g.id ? (
                  <>
                    <div className="cb-filter-chips mb-2">
                      {INPUT_CHIPS.map((chip) => (
                        <button
                          key={chip.id}
                          type="button"
                          className={`cb-filter-chip${inputType === chip.id ? ' is-active' : ''}`}
                          onClick={() => setInputType(chip.id)}
                        >
                          {chip.label}
                        </button>
                      ))}
                    </div>
                    <textarea
                      rows={3}
                      maxLength={2000}
                      placeholder="Optional comment"
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                    />
                    <div className="flex gap-2 mt-2">
                      <button
                        type="button"
                        className="cb-btn cb-btn--primary"
                        disabled={submitting}
                        onClick={() => submitInput(g)}
                      >
                        Send to team
                      </button>
                      <button type="button" className="cb-btn" onClick={() => setActiveGoal(null)}>
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  <button type="button" className="cb-btn" onClick={() => setActiveGoal(g.id)}>
                    {g.parent_input_prompt || 'Share your input'}
                  </button>
                )}
              </div>
            ) : null}

            {g.last_shared_date ? (
              <p className="mt-3 text-xs text-slate-400">Last shared {formatDisplayDate(g.last_shared_date)}</p>
            ) : null}
          </article>
        ))}
      </div>

      {!items.length ? <p className="gs-muted">Shared goals will appear here when the team publishes them.</p> : null}
    </div>
  )
}
