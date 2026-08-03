import { useState } from 'react'
import { sendGoalCandidateForReview } from '../../../lib/voiceLogApi.js'
import { dismissEmergingGoal, emergingGoals, markGoalCandidateSent } from '../../../lib/structuredSessionEvidence.js'

/**
 * Emerging goal candidates — AI-observed patterns without an IEP match.
 * Never counted as goal evidence, never in the family update.
 * Therapist can edit, dismiss, or send to the case manager review queue.
 */
export function EmergingGoalCandidates({ structuredSession, onChange, caseId, sessionId, embedded = false }) {
  const candidates = emergingGoals(structuredSession)
  const [busyLabel, setBusyLabel] = useState(null)
  const [notice, setNotice] = useState('')

  if (!candidates.length) return null

  function updateCandidate(goal, patch) {
    const goals = (structuredSession.goals || []).map((g) => (g === goal ? { ...g, ...patch } : g))
    onChange({ ...structuredSession, goals })
  }

  async function sendToCm(goal) {
    setBusyLabel(goal.goal_label)
    setNotice('')
    // Optimistic: mark sent locally first, reconcile with API result.
    onChange(markGoalCandidateSent(structuredSession, goal, null))
    try {
      const created = await sendGoalCandidateForReview(caseId, {
        label: goal.goal_label,
        rationale: goal.source_transcript_excerpt || undefined,
        sessionId,
        note: goal.therapist_note || undefined,
      })
      setNotice(`Sent to your case manager for review: ${goal.goal_label}`)
      onChange((prev) => {
        const goals = (prev.goals || []).map((g) =>
          g.goal_label === goal.goal_label && g.match_type === 'new_observation'
            ? { ...g, candidate_id: created?.id ?? null, candidate_status: 'pending_review' }
            : g,
        )
        const goal_candidates = (prev.goal_candidates || []).map((c) =>
          c.label === goal.goal_label && !c.candidate_id ? { ...c, candidate_id: created?.id ?? null } : c,
        )
        return { ...prev, goals, goal_candidates }
      })
    } catch (err) {
      setNotice(err.message || 'Could not reach the review queue — the suggestion is still saved with this log.')
    } finally {
      setBusyLabel(null)
    }
  }

  return (
    <section className={embedded ? '' : 'vsl-stitch__card'} aria-label="Emerging goal suggestions">
      {!embedded ? (
        <>
          <h3 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
            Suggest a new goal
          </h3>
          <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '0 0 10px' }}>
            Work noticed today that is not on the IEP yet. Send to your case manager to consider adding to the plan.
          </p>
        </>
      ) : null}
      {candidates.map((goal, i) => {
        const sent = goal.candidate_status === 'pending_review'
        return (
          <article key={`${goal.goal_label}-${i}`} className="vsl-stitch__goal-card">
            <div className="vsl-stitch__badges">
              <span className="vsl-stitch__badge">New goal idea</span>
              {sent ? <span className="vsl-stitch__badge vsl-stitch__badge--review">Sent for CM review</span> : null}
            </div>
            <input
              className="vsl-stitch__input"
              value={goal.goal_label}
              maxLength={300}
              aria-label="Suggested goal title"
              onChange={(e) => updateCandidate(goal, { goal_label: e.target.value })}
              disabled={sent}
            />
            {goal.source_transcript_excerpt ? (
              <div className="vsl-stitch__transcript-box">You said: &ldquo;{goal.source_transcript_excerpt}&rdquo;</div>
            ) : null}
            <textarea
              className="vsl-stitch__textarea"
              rows={2}
              maxLength={500}
              placeholder="Optional note for your case manager"
              value={goal.therapist_note || ''}
              onChange={(e) => updateCandidate(goal, { therapist_note: e.target.value })}
              disabled={sent}
            />
            {!sent ? (
              <div className="vsl-stitch__chip-row" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="vsl-stitch__chip vsl-stitch__chip--on"
                  disabled={busyLabel === goal.goal_label || !goal.goal_label?.trim()}
                  onClick={() => sendToCm(goal)}
                >
                  {busyLabel === goal.goal_label ? 'Sending…' : 'Send for CM review'}
                </button>
                <button
                  type="button"
                  className="vsl-stitch__chip"
                  onClick={() => onChange(dismissEmergingGoal(structuredSession, goal))}
                >
                  Dismiss
                </button>
              </div>
            ) : null}
          </article>
        )
      })}
      {notice ? (
        <p role="status" style={{ fontSize: '0.8125rem', margin: '8px 0 0' }}>
          {notice}
        </p>
      ) : null}
    </section>
  )
}
