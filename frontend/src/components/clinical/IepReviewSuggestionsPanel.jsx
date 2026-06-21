import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { IEP_REVIEW_SUGGESTIONS } from '../../lib/reportsRevampFlags.js'
import { currentMonthValue } from '../../lib/insightsConstants.js'
import { ClinicalSecondaryButton } from '../clinical-ui/ClinicalSecondaryButton.jsx'

export function IepReviewSuggestionsPanel({ caseId, onUpdated }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!IEP_REVIEW_SUGGESTIONS) {
      setItems([])
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/iep-review-suggestions`)
      setItems(data.items || [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  async function dismiss(id) {
    await apiFetch(`/api/v1/cases/${caseId}/iep-review-suggestions/${id}/dismiss`, { method: 'POST' })
    await load()
    onUpdated?.()
  }

  async function accept(id) {
    await apiFetch(`/api/v1/cases/${caseId}/iep-review-suggestions/${id}/accept`, { method: 'POST' })
    await load()
    onUpdated?.()
  }

  async function generateAiSuggestions() {
    setLoading(true)
    try {
      await apiFetch(`/api/v1/cases/${caseId}/iep/ai/review-suggestions?month=${currentMonthValue()}`, {
        method: 'POST',
      })
      await load()
    } finally {
      setLoading(false)
    }
  }

  if (!IEP_REVIEW_SUGGESTIONS) return null
  if (loading) return <p className="ic-case-panel__loading">Loading IEP suggestions…</p>
  if (!items.length) return (
    <div className="clinical-empty-state">
      <span className="clinical-empty-state__icon">📋</span>
      <p className="clinical-empty-state__title">No IEP suggestions yet</p>
      <p className="clinical-empty-state__body">Generate suggestions from saved session evidence and monthly snapshots.</p>
      <ClinicalSecondaryButton onClick={generateAiSuggestions}>Generate IEP Review Suggestions</ClinicalSecondaryButton>
    </div>
  )

  return (
    <section className="cp-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
        <h4>IEP review suggestions</h4>
        <ClinicalSecondaryButton onClick={generateAiSuggestions}>Generate IEP Review Suggestions</ClinicalSecondaryButton>
      </div>
      <ul className="cp-goal-list">
        {items.map((s) => (
          <li key={s.id} className="cp-goal-card">
            <p>{s.reason}</p>
            <div className="cp-ai-preview__actions">
              <button type="button" className="ic-btn ic-btn--ghost ic-btn--sm" onClick={() => accept(s.id)}>
                Accept (draft goal)
              </button>
              <button type="button" className="ic-btn ic-btn--ghost ic-btn--sm" onClick={() => dismiss(s.id)}>
                Dismiss
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
