import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { emptyStrategyRow } from '../../../lib/clinicalScoring.js'

export function StrategyAlternativesPanel({ caseId, goalCardId, environment, excludeStrategyIds, onTryStrategy }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!caseId || !goalCardId) {
      setItems([])
      return
    }
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const exclude = (excludeStrategyIds || []).filter(Boolean).join(',')
        const qs = new URLSearchParams()
        if (environment) qs.set('environment', environment)
        if (exclude) qs.set('exclude', exclude)
        const data = await apiFetch(
          `/api/v1/cases/${caseId}/goals/${goalCardId}/strategy-suggestions?${qs.toString()}`
        )
        if (!cancelled) setItems(data.items || [])
      } catch {
        if (!cancelled) setItems([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [caseId, goalCardId, environment, excludeStrategyIds?.join(',')])

  if (!goalCardId) return null

  return (
    <div className="sl-alternatives">
      <p className="sl-alternatives__title">Try an alternative strategy</p>
      {loading ? <p className="gs-muted">Loading suggestions…</p> : null}
      {!loading && !items.length ? (
        <p className="gs-muted">No alternatives right now — add one from the strategy library.</p>
      ) : null}
      {items.map((item) => (
        <div key={`${item.strategy_id}-${item.label}`} className="sl-alternatives__item">
          <div>
            <p className="sl-alternatives__copy">{item.label}</p>
            <p className="sl-alternatives__why">{item.why_it_may_help}</p>
          </div>
          <button
            type="button"
            className="gs-btn gs-btn--ghost"
            onClick={() =>
              onTryStrategy?.({
                ...emptyStrategyRow(goalCardId),
                strategy_id: item.strategy_id,
                strategy_label: item.label,
              })
            }
          >
            Try this
          </button>
        </div>
      ))}
    </div>
  )
}
