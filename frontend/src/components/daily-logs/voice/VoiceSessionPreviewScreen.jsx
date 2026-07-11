import { useState } from 'react'
import {
  collectSessionStrategies,
  deriveSessionInsights,
  responseSignalLabel,
} from '../../../lib/structuredSessionEvidence.js'

const FEEDBACK_LABELS = {
  worked_well: 'Helpful',
  partially_worked: 'Partly helpful',
  did_not_work: 'Not helpful',
  not_observed: 'Not observed',
}

function BulletSection({ title, items }) {
  if (!items?.length) return null
  return (
    <section style={{ marginBottom: 20 }}>
      <h4 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
        {title}
      </h4>
      <ul className="vsl-stitch__preview-list">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </section>
  )
}

export function VoiceSessionPreviewScreen({ structuredSession, isLateSession, lateReason, onLateReasonChange, error }) {
  const [tab, setTab] = useState('parent')
  const pu = structuredSession.parent_update || {}

  const confirmed = (structuredSession.goals || []).filter(
    (g) => g.status === 'confirmed' || g.status === 'changed',
  )
  const strategies = collectSessionStrategies(structuredSession)
  const signals = structuredSession.child_response_signals || []
  const challenges = structuredSession.challenge_observations || []
  const goalCandidates = structuredSession.goal_candidates || []
  const strategyCandidates = structuredSession.strategy_candidates || []
  const insights = deriveSessionInsights(structuredSession)

  return (
    <div>
      <div className="vsl-stitch__tabs">
        <button
          type="button"
          className={`vsl-stitch__tab ${tab === 'parent' ? 'vsl-stitch__tab--active' : ''}`}
          onClick={() => setTab('parent')}
        >
          Family update
        </button>
        <button
          type="button"
          className={`vsl-stitch__tab ${tab === 'clinical' ? 'vsl-stitch__tab--active' : ''}`}
          onClick={() => setTab('clinical')}
        >
          Clinical record
        </button>
      </div>

      {tab === 'parent' ? (
        <div className="vsl-stitch__card" style={{ borderStyle: 'dashed' }}>
          <p style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--vsl-secondary)', margin: '0 0 12px' }}>
            Preview: what family will see
          </p>
          <BulletSection title="Today's Session" items={pu.todays_session} />
          <BulletSection title="Wins Today" items={pu.wins_today} />
          <BulletSection title="Helpful Supports" items={pu.helpful_supports} />
          <BulletSection title="Next Session" items={pu.next_session} />
          {!pu.todays_session?.length && structuredSession.parent_summary ? (
            <p style={{ lineHeight: 1.6 }}>{structuredSession.parent_summary}</p>
          ) : null}
          <p style={{ fontSize: '0.75rem', color: 'var(--vsl-secondary)', margin: '12px 0 0' }}>
            Internal notes, reflections, concerns, and pending suggestions are never shown here.
          </p>
        </div>
      ) : (
        <div className="vsl-stitch__card">
          <p className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
            Clinical summary (internal)
          </p>
          <p style={{ lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
            {structuredSession.clinical_summary || structuredSession.todays_story}
          </p>

          <BulletSection
            title={`Confirmed goals (${confirmed.length})`}
            items={confirmed.map((g) => g.goal_label)}
          />
          {structuredSession.no_goal_reason ? (
            <p style={{ fontSize: '0.875rem' }}>
              No IEP goal addressed — reason: {structuredSession.no_goal_reason.replace(/_/g, ' ')}
            </p>
          ) : null}
          <BulletSection
            title="Strategy events"
            items={strategies.map(
              (s) =>
                `${s.strategy_label}${s.feedback ? ` — ${FEEDBACK_LABELS[s.feedback] || s.feedback}` : ''}${s._goalLabel ? ` (goal: ${s._goalLabel})` : ''}`,
            )}
          />
          <BulletSection title="Child response signals" items={signals.map(responseSignalLabel)} />
          <BulletSection
            title="Challenges and concerns"
            items={challenges.map(
              (c) => `${c.text}${c.flag_cm_review ? ' — flagged for CM review' : ''}${c.incident_reported ? ' — incident report opened' : ''}`,
            )}
          />
          <BulletSection
            title="Sent to case manager"
            items={[
              ...goalCandidates.map((c) => `Goal candidate: ${c.label}`),
              ...strategyCandidates.map((c) => `Strategy candidate: ${c.label}`),
            ]}
          />
          <BulletSection title="Session insights (derived)" items={insights} />
          {structuredSession.therapist_reflection ? (
            <section style={{ marginBottom: 20 }}>
              <h4 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
                Therapist reflection (internal)
              </h4>
              <p style={{ lineHeight: 1.6 }}>{structuredSession.therapist_reflection}</p>
            </section>
          ) : null}
          {structuredSession.voice_transcript ? (
            <p style={{ fontSize: '0.75rem', color: 'var(--vsl-secondary)' }}>
              Transcript on file{structuredSession.recording_id ? ` · recording #${structuredSession.recording_id}` : ''}
              {structuredSession.extraction_version ? ` · extraction v${structuredSession.extraction_version}` : ''}
            </p>
          ) : null}
        </div>
      )}

      {isLateSession ? (
        <div className="vsl-stitch__banner vsl-stitch__banner--review">
          Past-day visit: add a late reason before submitting.
          <textarea
            className="vsl-stitch__textarea"
            style={{ marginTop: 10 }}
            placeholder="Why is this log late?"
            value={lateReason || ''}
            onChange={(e) => onLateReasonChange?.(e.target.value)}
          />
        </div>
      ) : null}

      {error ? <p className="vsl-stitch__error">{error}</p> : null}
    </div>
  )
}
