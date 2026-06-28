import { useEffect, useState } from 'react'
import { fetchIepEvidenceReview, sendIepSuggestionToReview } from '../../../lib/monthlyReportApi.js'
import { IEP_REVIEW_SUGGESTIONS } from '../../../lib/reportsRevampFlags.js'

export function IepReviewSuggestionsPanel({ caseId, iepPlanId }) {
  const [data, setData] = useState(null)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (!caseId || !IEP_REVIEW_SUGGESTIONS) return
    fetchIepEvidenceReview(caseId, iepPlanId)
      .then(setData)
      .catch(() => setData(null))
  }, [caseId, iepPlanId])

  if (!IEP_REVIEW_SUGGESTIONS) return null
  if (!data?.goal_evidence?.length) return null

  async function sendToReview(suggestionId) {
    setMsg('')
    try {
      await sendIepSuggestionToReview(suggestionId)
      setMsg('Added to CM review queue.')
    } catch (err) {
      setMsg(err.message || 'Could not add to review.')
    }
  }

  return (
    <section className="cb-card mt-4">
      <h3 className="cb-section__label">Review suggestions</h3>
      <p className="gs-muted text-sm">May need attention — for team discussion, not automatic decisions.</p>
      {msg ? <p className="gs-muted">{msg}</p> : null}
      {data.goal_evidence.map((g) => (
        <div key={g.goal_id} className="mt-3">
          <p className="font-semibold">{g.goal_title}</p>
          <p className="gs-muted text-sm">
            {g.sessions_addressed} sessions · {g.evidence_events} evidence events
          </p>
          {(g.review_suggestions || []).map((s) => (
            <article key={s.suggestion_id || s.type} className="mt-2 p-2 border rounded">
              <p className="text-sm">{s.reason}</p>
              <div className="flex gap-2 mt-2">
                {s.suggestion_id ? (
                  <button type="button" className="cb-btn cb-btn--primary" onClick={() => sendToReview(s.suggestion_id)}>
                    Add to CM review
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ))}
    </section>
  )
}
