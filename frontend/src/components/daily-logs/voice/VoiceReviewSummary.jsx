import { getReviewSummary } from '../../../lib/structuredSessionEvidence.js'

export function VoiceReviewSummary({ structuredSession }) {
  const summary = getReviewSummary(structuredSession)

  if (!summary.hasUnresolved && !summary.familyUpdatePending) {
    return (
      <div className="vsl-stitch__banner vsl-stitch__banner--success" role="status">
        <strong>Everything is reviewed — you can preview and submit.</strong>
      </div>
    )
  }

  return (
    <div className="vsl-stitch__banner vsl-stitch__banner--review" role="status">
      <strong>Review required</strong>
      <ul className="vsl-stitch__review-summary-list">
        {summary.pendingGoals > 0 ? (
          <li>
            {summary.pendingGoals} goal match{summary.pendingGoals > 1 ? 'es' : ''} to confirm or reject
          </li>
        ) : null}
        {summary.strategies > 0 ? (
          <li>
            {summary.strategies} strateg{summary.strategies > 1 ? 'ies' : 'y'} noted
          </li>
        ) : null}
        {summary.participationSignals + summary.strengths > 0 ? (
          <li>
            {summary.participationSignals} participation · {summary.strengths} strength
            {summary.strengths === 1 ? '' : 's'} signal{summary.participationSignals + summary.strengths > 1 ? 's' : ''}
          </li>
        ) : null}
        {summary.challenges > 0 ? <li>{summary.challenges} challenge summary</li> : null}
        {summary.familyUpdatePending ? <li>Family update will build from confirmed evidence at preview</li> : null}
      </ul>
    </div>
  )
}
