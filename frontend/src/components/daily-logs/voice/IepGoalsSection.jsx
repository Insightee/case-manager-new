import { useState } from 'react'
import {
  buildIepGoalReviewList,
  matchLabelFromConfidence,
  selectIepGoalForSession,
  updateGoal,
} from '../../../lib/structuredSessionEvidence.js'

function goalEvidenceDisplay(goal) {
  const lines = (goal.evidence || []).map((line) => String(line || '').trim()).filter(Boolean)
  if (lines.length) return lines.join('\n')
  return goal.source_transcript_excerpt || ''
}

function findGoalIndex(session, goal) {
  const goals = session?.goals || []
  if (goal.goal_card_id != null) {
    const byId = goals.findIndex((g) => g.goal_card_id === goal.goal_card_id && g.match_type !== 'new_observation')
    if (byId >= 0) return byId
  }
  const label = (goal.goal_label || '').trim().toLowerCase()
  if (!label) return -1
  return goals.findIndex(
    (g) => g.match_type !== 'new_observation' && (g.goal_label || '').trim().toLowerCase() === label,
  )
}

function GoalReviewCard({ goal, onPatch, onConfirm, onReject, manual }) {
  const [expanded, setExpanded] = useState(goal.status === 'pending' || manual)
  const statusIcon =
    goal.status === 'confirmed' ? '✓' : goal.status === 'rejected' ? '×' : '○'

  function handleConfirm(e) {
    e.preventDefault()
    e.stopPropagation()
    onConfirm()
    setExpanded(true)
  }

  function handleReject(e) {
    e.preventDefault()
    e.stopPropagation()
    onReject()
    setExpanded(false)
  }

  return (
    <article className="vsl-stitch__timeline-card vsl-stitch__goal-details">
      <div className="vsl-stitch__goal-header">
        <div className="vsl-stitch__goal-header-top">
          <span className={`vsl-stitch__goal-status-icon vsl-stitch__goal-status-icon--${goal.status}`}>
            {statusIcon}
          </span>
          <div className="vsl-stitch__goal-header-copy">
            <div className="vsl-stitch__badges vsl-stitch__badges--compact">
              <span className="vsl-stitch__badge vsl-stitch__badge--mint">IEP goal</span>
              {goal.manually_selected ? (
                <span className="vsl-stitch__badge">Added by you</span>
              ) : (
                <span className="vsl-stitch__badge">{matchLabelFromConfidence(goal)}</span>
              )}
            </div>
            <h4 className="vsl-stitch__goal-title">{goal.goal_label}</h4>
          </div>
          <div className="vsl-stitch__goal-actions">
            <button
              type="button"
              className={`vsl-stitch__icon-btn ${goal.status === 'confirmed' ? 'vsl-stitch__icon-btn--on' : ''}`}
              title="Confirm goal"
              aria-label="Confirm goal"
              aria-pressed={goal.status === 'confirmed'}
              onClick={handleConfirm}
            >
              ✓
            </button>
            <button
              type="button"
              className={`vsl-stitch__icon-btn vsl-stitch__icon-btn--muted ${goal.status === 'rejected' ? 'vsl-stitch__icon-btn--on' : ''}`}
              title="Not relevant today"
              aria-label="Not relevant today"
              aria-pressed={goal.status === 'rejected'}
              onClick={handleReject}
            >
              ×
            </button>
          </div>
        </div>
        <button
          type="button"
          className="vsl-stitch__goal-expand"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? 'Hide session evidence' : 'Review session evidence'}
        </button>
      </div>
      {expanded ? (
        <div className="vsl-stitch__goal-body">
          {goal.source_transcript_excerpt && !manual ? (
            <p className="vsl-stitch__goal-transcript-hint">
              From your recording: &ldquo;{goal.source_transcript_excerpt.slice(0, 180)}
              {goal.source_transcript_excerpt.length > 180 ? '…' : ''}&rdquo;
            </p>
          ) : null}
          <label className="vsl-stitch__field-label">
            {manual ? 'What you worked on — add in your words' : 'How this goal showed up today'}
          </label>
          <textarea
            className="vsl-stitch__field vsl-stitch__field--inline vsl-stitch__field--goal"
            placeholder={
              manual
                ? 'Describe what you did for this goal today…'
                : 'Edit how this goal appeared in session — not a raw transcript paste.'
            }
            value={goalEvidenceDisplay(goal)}
            onChange={(e) =>
              onPatch({
                evidence: e.target.value.split('\n').filter(Boolean),
                source_transcript_excerpt: e.target.value.slice(0, 500),
              })
            }
          />
        </div>
      ) : null}
    </article>
  )
}

export function IepGoalsSection({ structuredSession, onChange, repo }) {
  const { active, available } = buildIepGoalReviewList(repo, structuredSession)
  const [showAllIep, setShowAllIep] = useState(false)

  function patchGoal(goal, patch) {
    const idx = findGoalIndex(structuredSession, goal)
    if (idx >= 0) onChange(updateGoal(structuredSession, idx, patch))
  }

  return (
    <section className="vsl-stitch__timeline-section">
      <h3 className="vsl-stitch__section-label">IEP goals today</h3>
      <p className="vsl-stitch__section-hint">
        Confirm matched goals or add others from your IEP — edit evidence in your words.
      </p>

      {active.length ? (
        active.map((g, i) => (
          <GoalReviewCard
            key={`${g.goal_card_id || g.goal_label}-${i}-${g.status}`}
            goal={g}
            manual={Boolean(g.manually_selected && !g.source_transcript_excerpt)}
            onPatch={(patch) => patchGoal(g, patch)}
            onConfirm={() => patchGoal(g, { status: 'confirmed' })}
            onReject={() => patchGoal(g, { status: 'rejected' })}
          />
        ))
      ) : (
        <p className="vsl-stitch__empty-hint">
          No goals matched from your recording yet — pick from your IEP below or note why no goal applied.
        </p>
      )}

      {available.length ? (
        <div className="vsl-stitch__iep-available">
          <button
            type="button"
            className="vsl-stitch__text-link"
            onClick={() => setShowAllIep((v) => !v)}
          >
            {showAllIep ? 'Hide' : 'Show'} other IEP goals ({available.length})
          </button>
          {showAllIep ? (
            <ul className="vsl-stitch__iep-list">
              {available.map((rg) => (
                <li key={rg.goal_card_id || rg.label} className="vsl-stitch__iep-list-item">
                  <span className="vsl-stitch__iep-list-label">{rg.label}</span>
                  <button
                    type="button"
                    className="vsl-stitch__pill vsl-stitch__pill--add"
                    onClick={() => onChange(selectIepGoalForSession(structuredSession, rg))}
                  >
                    Worked on today
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
