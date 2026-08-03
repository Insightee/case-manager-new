import { useState } from 'react'
import {
  NO_GOAL_REASONS,
  emergingGoals,
  getReviewSummary,
  setChallengeSummary,
  getChallengeSummary,
  getChallengeContext,
  updateChallengeFlags,
  strengthKeywords,
  addStrengthKeyword,
  removeStrengthKeyword,
  participationSignalsForDisplay,
  availableParticipationSignals,
  addParticipationSignal,
  removeParticipationSignal,
} from '../../../lib/structuredSessionEvidence.js'
import { IepGoalsSection } from './IepGoalsSection.jsx'
import { EmergingGoalCandidates } from './EmergingGoalCandidates.jsx'
import { StrategiesUsedSection } from './StrategiesUsedSection.jsx'
import { ClinicalBrainInsightPanel } from './ClinicalBrainInsightPanel.jsx'
import { VoiceReviewSummary } from './VoiceReviewSummary.jsx'

export function VoiceStoryDraftScreen({
  structuredSession,
  onChange,
  repo,
  caseId,
  sessionId,
  transcriptOpen,
  onToggleTranscript,
}) {
  const [strengthInput, setStrengthInput] = useState('')
  const [showMoreParticipation, setShowMoreParticipation] = useState(false)
  const summary = getReviewSummary(structuredSession)
  const emerging = emergingGoals(structuredSession)
  const confirmedCount = (structuredSession.goals || []).filter(
    (g) => g.status === 'confirmed' || g.status === 'changed',
  ).length
  const challengeText = getChallengeSummary(structuredSession)
  const challengeCtx = getChallengeContext(structuredSession)
  const strengths = strengthKeywords(structuredSession)
  const participation = participationSignalsForDisplay(structuredSession)
  const moreParticipation = availableParticipationSignals(structuredSession)

  return (
    <div className="vsl-stitch__timeline-feed">
      <div className="vsl-stitch__status-row">
        <span className="vsl-stitch__status-dot" aria-hidden="true" />
        <span className="vsl-stitch__status-text">Interpretation ready</span>
        {summary.hasUnresolved ? (
          <span className="vsl-stitch__status-hint">
            {summary.pendingGoals ? `${summary.pendingGoals} to review` : 'Review suggested items'}
          </span>
        ) : (
          <span className="vsl-stitch__status-hint vsl-stitch__status-hint--ok">Ready to preview</span>
        )}
      </div>

      <VoiceReviewSummary structuredSession={structuredSession} />

      <section className="vsl-stitch__timeline-card vsl-stitch__timeline-card--ai">
        <div className="vsl-stitch__card-head">
          <div className="vsl-stitch__card-icon vsl-stitch__card-icon--ai">✦</div>
          <h3 className="vsl-stitch__card-title">Today&apos;s session narrative</h3>
          <span className="vsl-stitch__ai-tag">AI mapped</span>
        </div>
        <textarea
          className="vsl-stitch__field vsl-stitch__field--narrative"
          rows={6}
          maxLength={4000}
          value={structuredSession.todays_story}
          placeholder="Your session story — edit freely. Filled from your voice note."
          onChange={(e) =>
            onChange({ ...structuredSession, todays_story: e.target.value, story_edited_by_therapist: true })
          }
        />
        {structuredSession.voice_transcript ? (
          <details className="vsl-stitch__transcript-details" open={transcriptOpen}>
            <summary onClick={(e) => { e.preventDefault(); onToggleTranscript?.(!transcriptOpen) }}>
              View transcript
            </summary>
            <p className="vsl-stitch__transcript-text">{structuredSession.voice_transcript}</p>
          </details>
        ) : null}
      </section>

      <IepGoalsSection structuredSession={structuredSession} onChange={onChange} repo={repo} />

      {confirmedCount === 0 ? (
        <div className="vsl-stitch__no-goal vsl-stitch__timeline-card">
          <p className="vsl-stitch__field-label">No IEP goal addressed today?</p>
          <div className="vsl-stitch__pill-row">
            {NO_GOAL_REASONS.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`vsl-stitch__pill ${structuredSession.no_goal_reason === r.id ? 'vsl-stitch__pill--on' : ''}`}
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

      {emerging.length ? (
        <section className="vsl-stitch__timeline-card vsl-stitch__timeline-card--emerging">
          <div className="vsl-stitch__card-head">
            <div className="vsl-stitch__card-icon">◎</div>
            <h3 className="vsl-stitch__card-title">New goal ideas from today</h3>
            <span className="vsl-stitch__ai-tag">Not on IEP yet</span>
          </div>
          <p className="vsl-stitch__section-hint">
            Your session mentioned work that isn&apos;t on the current IEP — for example a new skill area like maths.
            Review and suggest adding as a goal for case manager approval.
          </p>
          <EmergingGoalCandidates
            structuredSession={structuredSession}
            onChange={onChange}
            caseId={caseId}
            sessionId={sessionId}
            embedded
          />
        </section>
      ) : null}

      <div className="vsl-stitch__grid-2">
        <section className="vsl-stitch__timeline-card">
          <div className="vsl-stitch__card-head">
            <div className="vsl-stitch__card-icon">◈</div>
            <h3 className="vsl-stitch__card-title">Strategies used</h3>
          </div>
          <StrategiesUsedSection
            structuredSession={structuredSession}
            onChange={onChange}
            repo={repo}
            caseId={caseId}
          />
        </section>

        <section className="vsl-stitch__timeline-card">
          <div className="vsl-stitch__card-head">
            <div className="vsl-stitch__card-icon">◉</div>
            <h3 className="vsl-stitch__card-title">Participation</h3>
          </div>
          {participation.length ? (
            <div className="vsl-stitch__pill-row">
              {participation.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="vsl-stitch__pill vsl-stitch__pill--mint"
                  onClick={() => onChange(removeParticipationSignal(structuredSession, s.id))}
                  title="Remove"
                >
                  {s.label} ×
                </button>
              ))}
            </div>
          ) : (
            <p className="vsl-stitch__empty-hint">Participation signals from your recording will appear here.</p>
          )}
          {moreParticipation.length ? (
            <>
              <button
                type="button"
                className="vsl-stitch__text-link"
                style={{ marginTop: 8 }}
                onClick={() => setShowMoreParticipation((v) => !v)}
              >
                {showMoreParticipation ? 'Hide' : 'Add'} participation signal
              </button>
              {showMoreParticipation ? (
                <div className="vsl-stitch__pill-row" style={{ marginTop: 8 }}>
                  {moreParticipation.slice(0, 8).map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className="vsl-stitch__pill vsl-stitch__pill--add"
                      onClick={() => {
                        onChange(addParticipationSignal(structuredSession, s.id))
                        setShowMoreParticipation(false)
                      }}
                    >
                      + {s.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </>
          ) : null}

          <div style={{ marginTop: 16 }}>
            <p className="vsl-stitch__field-label">Strengths noticed</p>
            {strengths.length ? (
              <div className="vsl-stitch__pill-row">
                {strengths.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="vsl-stitch__pill vsl-stitch__pill--strength"
                    onClick={() => onChange(removeStrengthKeyword(structuredSession, s))}
                  >
                    {s} ×
                  </button>
                ))}
              </div>
            ) : (
              <p className="vsl-stitch__empty-hint">Strength keywords from your session will appear here.</p>
            )}
            <div className="vsl-stitch__keyword-add">
              <input
                className="vsl-stitch__field vsl-stitch__field--search"
                placeholder="Add strength keyword…"
                value={strengthInput}
                maxLength={80}
                onChange={(e) => setStrengthInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && strengthInput.trim()) {
                    e.preventDefault()
                    onChange(addStrengthKeyword(structuredSession, strengthInput))
                    setStrengthInput('')
                  }
                }}
              />
            </div>
          </div>
        </section>
      </div>

      {(structuredSession.support_signals || []).length ? (
        <section className="vsl-stitch__timeline-card">
          <p className="vsl-stitch__section-label">Supports leveraged</p>
          <div className="vsl-stitch__pill-row">
            {structuredSession.support_signals.map((s, i) => (
              <span key={i} className="vsl-stitch__support-pill">
                {s.label}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <section
        className={`vsl-stitch__timeline-card ${challengeCtx.aiSuggested ? 'vsl-stitch__timeline-card--highlight' : ''}`}
      >
        <div className="vsl-stitch__card-head">
          <p className="vsl-stitch__section-label" style={{ margin: 0 }}>
            Challenges or barriers observed
          </p>
          {challengeCtx.aiSuggested ? (
            <span className="vsl-stitch__badge vsl-stitch__badge--review">From your recording</span>
          ) : null}
        </div>
        {(challengeCtx.environment || challengeCtx.childLevel) && challengeText.trim() ? (
          <div className="vsl-stitch__pill-row" style={{ marginBottom: 10 }}>
            {challengeCtx.environment ? (
              <span className="vsl-stitch__barrier-pill vsl-stitch__barrier-pill--env">Environment barrier</span>
            ) : null}
            {challengeCtx.childLevel ? (
              <span className="vsl-stitch__barrier-pill vsl-stitch__barrier-pill--child">Support moment</span>
            ) : null}
          </div>
        ) : null}
        <textarea
          className="vsl-stitch__field vsl-stitch__field--inline"
          rows={3}
          maxLength={1200}
          placeholder="Barriers, sensory context, or support moments — edit in neuro-affirming language."
          value={challengeText}
          onChange={(e) => onChange(setChallengeSummary(structuredSession, e.target.value))}
        />
        {challengeText.trim() ? (
          <div className="vsl-stitch__pill-row" style={{ marginTop: 8 }}>
            <button
              type="button"
              className={`vsl-stitch__pill ${challengeCtx.flagCm ? 'vsl-stitch__pill--review' : ''}`}
              onClick={() =>
                onChange(updateChallengeFlags(structuredSession, { flag_cm_review: !challengeCtx.flagCm }))
              }
            >
              Flag for CM review
            </button>
          </div>
        ) : null}
      </section>

      <section className="vsl-stitch__timeline-card vsl-stitch__timeline-card--brain">
        <div className="vsl-stitch__card-head">
          <div className="vsl-stitch__card-icon vsl-stitch__card-icon--brain">◆</div>
          <h3 className="vsl-stitch__card-title vsl-stitch__card-title--light">Clinical Brain insights</h3>
        </div>
        <ClinicalBrainInsightPanel structuredSession={structuredSession} compact />
      </section>

      <section className="vsl-stitch__timeline-card">
        <p className="vsl-stitch__section-label">Therapist reflection (internal)</p>
        <textarea
          className="vsl-stitch__field vsl-stitch__field--inline"
          maxLength={500}
          rows={2}
          placeholder="Optional — not shared with families"
          value={structuredSession.therapist_reflection || ''}
          onChange={(e) => onChange({ ...structuredSession, therapist_reflection: e.target.value || null })}
        />
      </section>
    </div>
  )
}
