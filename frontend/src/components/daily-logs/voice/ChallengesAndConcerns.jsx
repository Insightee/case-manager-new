import { Link } from 'react-router-dom'
import {
  addChallenge,
  removeChallenge,
  updateChallenge,
} from '../../../lib/structuredSessionEvidence.js'

/**
 * Challenges or concerns noticed (optional). AI drafts entries from the
 * recording; every entry stays editable. Escalation is always a deliberate
 * therapist action — incidents are never auto-created.
 */
export function ChallengesAndConcerns({ structuredSession, onChange, caseId, sessionId }) {
  const entries = structuredSession.challenge_observations || []

  const incidentHref = `/therapist/support?tab=incidents&case_id=${caseId || ''}&session_id=${sessionId || ''}`

  return (
    <section className="vsl-stitch__card" aria-label="Challenges or concerns noticed">
      <h3 className="vsl-stitch__section-head" style={{ marginTop: 0 }}>
        Challenges or concerns noticed <span style={{ fontWeight: 400 }}>(optional)</span>
      </h3>
      {entries.length === 0 ? (
        <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '0 0 8px' }}>
          Nothing noted. Add a concern if something needs follow-up.
        </p>
      ) : null}
      {entries.map((entry, i) => (
        <article key={i} className="vsl-stitch__goal-card">
          {entry.source === 'ai' ? (
            <div className="vsl-stitch__badges">
              <span className="vsl-stitch__badge">Drafted from your update</span>
            </div>
          ) : null}
          <textarea
            className="vsl-stitch__textarea"
            rows={2}
            maxLength={800}
            value={entry.text}
            aria-label={`Concern ${i + 1}`}
            onChange={(e) => onChange(updateChallenge(structuredSession, i, { text: e.target.value }))}
          />
          <div className="vsl-stitch__chip-row" style={{ marginTop: 8 }}>
            <button
              type="button"
              className={`vsl-stitch__chip ${!entry.flag_cm_review ? 'vsl-stitch__chip--on' : ''}`}
              onClick={() => onChange(updateChallenge(structuredSession, i, { flag_cm_review: false }))}
            >
              Session observation
            </button>
            <button
              type="button"
              className={`vsl-stitch__chip ${entry.flag_cm_review ? 'vsl-stitch__chip--on' : ''}`}
              onClick={() => onChange(updateChallenge(structuredSession, i, { flag_cm_review: true }))}
            >
              Flag for CM review
            </button>
            <Link
              className="vsl-stitch__chip"
              to={incidentHref}
              onClick={() => onChange(updateChallenge(structuredSession, i, { incident_reported: true }))}
            >
              Create incident report
            </Link>
            <button
              type="button"
              className="vsl-stitch__chip"
              onClick={() => onChange(removeChallenge(structuredSession, i))}
            >
              Remove
            </button>
          </div>
          {entry.flag_cm_review ? (
            <p style={{ fontSize: '0.75rem', color: 'var(--vsl-secondary)', margin: '6px 0 0' }}>
              Your case manager will see this with the submitted log.
            </p>
          ) : null}
        </article>
      ))}
      <button
        type="button"
        className="vsl-stitch__btn vsl-stitch__btn--ghost"
        style={{ width: 'auto', marginTop: 4 }}
        onClick={() => onChange(addChallenge(structuredSession))}
      >
        + Add a concern
      </button>
    </section>
  )
}
