import { Link } from 'react-router-dom'
import {
  getChallengeSummary,
  setChallengeSummary,
  updateChallengeFlags,
} from '../../../lib/structuredSessionEvidence.js'

/**
 * One concise editable summary for challenges or barriers (V2).
 * Escalation is always deliberate — never auto-created.
 */
export function ChallengesAndConcerns({ structuredSession, onChange, caseId, sessionId }) {
  const summary = getChallengeSummary(structuredSession)
  const flags = structuredSession.challenge_observations?.[0] || {}
  const incidentHref = `/therapist/support?tab=incidents&case_id=${caseId || ''}&session_id=${sessionId || ''}`

  return (
    <div aria-label="Challenges or barriers observed">
      <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '0 0 8px' }}>
        AI drafted · Therapist editable. Ordinary session challenges do not need escalation.
      </p>
      <textarea
        className="vsl-stitch__textarea"
        rows={3}
        maxLength={1200}
        placeholder="e.g. Increased kitchen noise made continued participation more difficult. They used a brief break before returning."
        value={summary}
        aria-label="Challenges or barriers observed"
        onChange={(e) => onChange(setChallengeSummary(structuredSession, e.target.value))}
      />
      {summary.trim() ? (
        <div className="vsl-stitch__chip-row" style={{ marginTop: 10 }}>
          <button
            type="button"
            className={`vsl-stitch__chip ${flags.flag_cm_review ? 'vsl-stitch__chip--on' : ''}`}
            onClick={() =>
              onChange(updateChallengeFlags(structuredSession, { flag_cm_review: !flags.flag_cm_review }))
            }
          >
            Flag for CM review
          </button>
          <Link
            className="vsl-stitch__chip"
            to={incidentHref}
            onClick={() => onChange(updateChallengeFlags(structuredSession, { incident_reported: true }))}
          >
            Start incident report
          </Link>
        </div>
      ) : null}
      {flags.flag_cm_review ? (
        <p style={{ fontSize: '0.75rem', color: 'var(--vsl-secondary)', margin: '8px 0 0' }}>
          Your case manager will review this with the submitted log.
        </p>
      ) : null}
    </div>
  )
}
