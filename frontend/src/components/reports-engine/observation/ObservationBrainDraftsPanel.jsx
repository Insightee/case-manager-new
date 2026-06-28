import { useState } from 'react'
import { fetchClinicalBrainEvidence } from '../../../lib/clinicalEvidenceApi.js'

export function ObservationBrainDraftsPanel({ reportId, readOnly = false }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function loadSummary() {
    if (!reportId) return
    setLoading(true)
    setError('')
    try {
      const data = await fetchClinicalBrainEvidence(reportId)
      setSummary(data)
    } catch (err) {
      setError(err.message || 'Could not load clinical brain summary')
    } finally {
      setLoading(false)
    }
  }

  const gaps = summary?.evidence_gaps || []
  const drafts = summary?.suggested_drafts || []

  return (
    <aside className="ob-brain-panel bg-surface-container-lowest p-4 sm:p-6 rounded-xl clinical-shadow border border-outline-variant/30 lg:sticky lg:top-4">
      <h3 className="text-lg font-bold text-lush-forest m-0 mb-2">Clinical Brain drafts</h3>
      <p className="text-xs text-on-surface-variant m-0 mb-4">
        Suggestions only — accept or edit before anything reaches the IEP.
      </p>

      {!readOnly ? (
        <button
          type="button"
          className="min-h-[44px] w-full rounded-xl bg-lush-forest text-white text-sm font-semibold mb-4"
          disabled={loading || !reportId}
          onClick={loadSummary}
        >
          {loading ? 'Reviewing evidence…' : 'Run clinical review'}
        </button>
      ) : null}

      {error ? <p className="text-sm text-error m-0 mb-3">{error}</p> : null}

      {summary ? (
        <div className="space-y-3 text-sm">
          <p className="m-0">
            <strong>{summary.materialized_event_count || 0}</strong> materialized events from{' '}
            <strong>{summary.session_log_count || 0}</strong> logs
          </p>
          {gaps.length ? (
            <div>
              <p className="font-semibold m-0 mb-1">Evidence gaps</p>
              <ul className="m-0 pl-4">
                {gaps.map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {drafts.length ? (
            <div>
              <p className="font-semibold m-0 mb-1">Suggested rows</p>
              <ul className="m-0 p-0 list-none space-y-2">
                {drafts.map((row) => (
                  <li key={row.id} className="rounded-lg border border-outline-variant/40 p-3">
                    <p className="m-0 font-medium">{row.label}</p>
                    <p className="text-xs text-on-surface-variant m-0 mt-1">{row.source_count} evidence sources</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-on-surface-variant m-0">No draft rows yet — run clinical review after adding observation evidence.</p>
          )}
        </div>
      ) : (
        <p className="text-sm text-on-surface-variant m-0">Tap run clinical review when you want evidence-based suggestions.</p>
      )}
    </aside>
  )
}
