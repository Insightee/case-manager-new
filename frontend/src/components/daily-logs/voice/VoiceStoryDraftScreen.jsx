import { useState } from 'react'
import {
  NO_GOAL_REASONS,
  aiMatchedGoals,
  deriveSessionInsights,
  getDraftReviewItems,
  toggleObservation,
  updateGoal,
} from '../../../lib/structuredSessionEvidence.js'
import { addGoalFromRepo } from '../../../lib/voiceExtractionMapper.js'
import { EmergingGoalCandidates } from './EmergingGoalCandidates.jsx'
import { StrategiesUsedSection } from './StrategiesUsedSection.jsx'
import { ChildResponseSection } from './ChildResponseSection.jsx'
import { ChallengesAndConcerns } from './ChallengesAndConcerns.jsx'

function GoalCard({ goal, onConfirm, onReject }) {
  const resolved = goal.status !== 'pending'
  return (
    <article
      className={`vsl-stitch__goal-card ${goal.status === 'confirmed' ? 'vsl-stitch__goal-card--confirmed' : ''}`}
    >
      <div className="vsl-stitch__badges">
        <span className="vsl-stitch__badge">
          {goal.match_type === 'active_iep' ? 'Active IEP goal' : 'AI suggested'}
        </span>
        {goal.confidence > 0 ? (
          <span className="vsl-stitch__badge">{Math.round(goal.confidence * 100)}% match</span>
        ) : null}
        {goal.status === 'pending' ? (
          <span className="vsl-stitch__badge vsl-stitch__badge--review">Needs review</span>
        ) : null}
        {goal.status === 'rejected' ? <span className="vsl-stitch__badge">Rejected</span> : null}
      </div>
      <h4 style={{ margin: '0 0 8px' }}>{goal.goal_label}</h4>
      {goal.source_transcript_excerpt ? (
        <div className="vsl-stitch__transcript-box">You said: &ldquo;{goal.source_transcript_excerpt}&rdquo;</div>
      ) : null}
      {goal.evidence?.length ? (
        <ul style={{ margin: '8px 0', paddingLeft: 18, fontSize: '0.875rem' }}>
          {goal.evidence.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      ) : null}
      <div className="vsl-stitch__chip-row">
        <button
          type="button"
          className={`vsl-stitch__chip ${goal.status === 'confirmed' ? 'vsl-stitch__chip--on' : ''}`}
          onClick={onConfirm}
        >
          {goal.status === 'confirmed' ? 'Confirmed' : 'Confirm'}
        </button>
        <button
          type="button"
          className={`vsl-stitch__chip ${goal.status === 'rejected' ? 'vsl-stitch__chip--on' : ''}`}
          onClick={onReject}
        >
          {goal.status === 'rejected' ? 'Rejected' : 'Reject'}
        </button>
      </div>
      {!resolved ? (
        <p style={{ fontSize: '0.75rem', color: 'var(--vsl-secondary)', margin: '6px 0 0' }}>
          Confirm if this goal was genuinely worked on today; reject if the match is wrong.
        </p>
      ) : null}
    </article>
  )
}

export function VoiceStoryDraftScreen({
  structuredSession,
  onChange,
  repo,
  caseId,
  sessionId,
  transcriptOpen,
  onToggleTranscript,
}) {
  const [goalSearch, setGoalSearch] = useState('')
  const reviewItems = getDraftReviewItems(structuredSession)
  const insights = deriveSessionInsights(structuredSession)
  const matched = aiMatchedGoals(structuredSession)
  const confirmedCount = (structuredSession.goals || []).filter(
    (g) => g.status === 'confirmed' || g.status === 'changed',
  ).length

  function setGoal(goal, patch) {
    const idx = structuredSession.goals.indexOf(goal)
    if (idx >= 0) onChange(updateGoal(structuredSession, idx, patch))
  }

  const usedLabels = new Set((structuredSession.goals || []).map((g) => (g.goal_label || '').toLowerCase()))
  const searchResults = goalSearch.trim()
    ? (repo?.goals || [])
        .filter(
          (g) =>
            !usedLabels.has((g.label || '').toLowerCase()) &&
            (g.label || '').toLowerCase().includes(goalSearch.trim().toLowerCase()),
        )
        .slice(0, 5)
    : []

  return (
    <div>
      {reviewItems.length > 0 ? (
        <div className="vsl-stitch__banner vsl-stitch__banner--review" role="status">
          <strong>
            {reviewItems.length} item{reviewItems.length > 1 ? 's' : ''} to review before submitting
          </strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: '0.8125rem' }}>
            {reviewItems.map((item, i) => (
              <li key={i}>{item.label}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="vsl-stitch__banner vsl-stitch__banner--success" role="status">
          <strong>Everything is reviewed — you can preview and submit.</strong>
        </div>
      )}

      <section className="vsl-stitch__card">
        <h3 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
          What happened today?
        </h3>
        <textarea
          className="vsl-stitch__textarea"
          rows={5}
          maxLength={4000}
          value={structuredSession.todays_story}
          placeholder="A short account of today's session — AI drafted this from your recording; adjust freely."
          onChange={(e) =>
            onChange({ ...structuredSession, todays_story: e.target.value, story_edited_by_therapist: true })
          }
        />
      </section>

      {structuredSession.voice_transcript ? (
        <details open={transcriptOpen} onToggle={(e) => onToggleTranscript?.(e.target.open)}>
          <summary>View transcript</summary>
          <p style={{ fontSize: '0.875rem', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
            {structuredSession.voice_transcript}
          </p>
        </details>
      ) : null}

      <section aria-label="Goals worked on">
        <h3 className="vsl-stitch__section-head">Goals worked on</h3>
        {matched.length ? (
          matched.map((g, i) => (
            <GoalCard
              key={`${g.goal_card_id || g.goal_label}-${i}`}
              goal={g}
              onConfirm={() => setGoal(g, { status: 'confirmed' })}
              onReject={() => setGoal(g, { status: 'rejected' })}
            />
          ))
        ) : (
          <p style={{ color: 'var(--vsl-secondary)', fontSize: '0.875rem' }}>
            No active IEP goals matched from your update.
          </p>
        )}

        <input
          className="vsl-stitch__input"
          placeholder="Search IEP goals to add…"
          value={goalSearch}
          onChange={(e) => setGoalSearch(e.target.value)}
          aria-label="Search IEP goals"
        />
        {searchResults.length ? (
          <div className="vsl-stitch__chip-row" style={{ marginTop: 8 }}>
            {searchResults.map((g) => (
              <button
                key={g.goal_card_id || g.label}
                type="button"
                className="vsl-stitch__chip"
                onClick={() => {
                  onChange(addGoalFromRepo(structuredSession, g))
                  setGoalSearch('')
                }}
              >
                + {g.label}
              </button>
            ))}
          </div>
        ) : null}

        {confirmedCount === 0 ? (
          <div style={{ marginTop: 12 }}>
            <p className="vsl-stitch__group-label">No IEP goal addressed today? Tell us why:</p>
            <div className="vsl-stitch__chip-row">
              {NO_GOAL_REASONS.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className={`vsl-stitch__chip ${structuredSession.no_goal_reason === r.id ? 'vsl-stitch__chip--on' : ''}`}
                  onClick={() =>
                    onChange({
                      ...structuredSession,
                      no_goal_reason: structuredSession.no_goal_reason === r.id ? null : r.id,
                    })
                  }
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <EmergingGoalCandidates
        structuredSession={structuredSession}
        onChange={onChange}
        caseId={caseId}
        sessionId={sessionId}
      />

      <StrategiesUsedSection
        structuredSession={structuredSession}
        onChange={onChange}
        repo={repo}
        caseId={caseId}
      />

      <ChildResponseSection structuredSession={structuredSession} onChange={onChange} />

      <ChallengesAndConcerns
        structuredSession={structuredSession}
        onChange={onChange}
        caseId={caseId}
        sessionId={sessionId}
      />

      {structuredSession.observations?.strengths?.length ? (
        <section aria-label="Strengths noticed">
          <h3 className="vsl-stitch__section-head">Strengths noticed</h3>
          <div className="vsl-stitch__chip-row">
            {structuredSession.observations.strengths.map((s) => (
              <button
                key={s}
                type="button"
                className="vsl-stitch__chip vsl-stitch__chip--on"
                onClick={() => onChange(toggleObservation(structuredSession, 'strengths', s))}
                title="Tap to remove"
              >
                {s}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {insights.length ? (
        <section className="vsl-stitch__card" aria-label="Therapist insights">
          <h3 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
            Session insights
          </h3>
          <p style={{ fontSize: '0.75rem', color: 'var(--vsl-secondary)', margin: '0 0 8px' }}>
            Drawn from what you confirmed today. Single-session signals only — never shared with families.
          </p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.875rem', lineHeight: 1.6 }}>
            {insights.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="vsl-stitch__card">
        <h3 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
          Therapist reflection
        </h3>
        <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '0 0 8px' }}>
          Optional — internal only, not shared with families (max 500 characters)
        </p>
        <textarea
          className="vsl-stitch__textarea"
          maxLength={500}
          placeholder="Something that surprised me, what worked, supervision notes…"
          value={structuredSession.therapist_reflection || ''}
          onChange={(e) => onChange({ ...structuredSession, therapist_reflection: e.target.value || null })}
        />
      </section>
    </div>
  )
}
