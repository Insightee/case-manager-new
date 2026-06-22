import { AI_ENABLED } from '../../../lib/reportsRevampFlags.js'

/** AI Strategy Lab shell — Generate disabled unless AI_ENABLED. */
export function AiStrategyLabPanel({ caseId }) {
  return (
    <section className="gs-ai-lab gs-engine" aria-labelledby="gs-ai-lab-title">
      <h3 id="gs-ai-lab-title" className="gs-ai-lab__title">
        AI Strategy Lab
      </h3>
      <p className="gs-ai-lab__note">
        Rule-based alternatives appear in session logs when strategy feedback is negative.
        AI generation stays off until your org enables it.
      </p>
      <button type="button" className="gs-btn gs-btn--primary" disabled={!AI_ENABLED}>
        {AI_ENABLED ? 'Generate suggestions' : 'Generate (coming soon)'}
      </button>
      {!AI_ENABLED ? (
        <p className="gs-muted" style={{ marginTop: '0.75rem' }}>
          Case {caseId ? `#${caseId}` : ''} — use session log strategy picker for curated alternatives.
        </p>
      ) : null}
    </section>
  )
}
