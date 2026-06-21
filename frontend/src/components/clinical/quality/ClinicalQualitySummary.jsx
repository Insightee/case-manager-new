import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { DocumentationHealthCard } from './DocumentationHealthCard.jsx'
import { EvidenceCompletenessCard } from './EvidenceCompletenessCard.jsx'
import { PendingActionsCard } from './PendingActionsCard.jsx'
import { ReportTimelineCard } from './ReportTimelineCard.jsx'

export function ClinicalQualitySummary({ caseId, variant = 'therapist', compact = false }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/clinical-quality-summary`)
      setSummary(data)
    } catch (err) {
      setError(err.message || 'Could not load quality summary')
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <p className="ic-case-panel__loading">Loading documentation quality…</p>
  if (error) return <p className="ic-case-panel__error">{error}</p>
  if (!summary) return null

  return (
    <div className={`clinical-quality-grid${compact ? ' clinical-quality-grid--compact' : ''}`}>
      <DocumentationHealthCard summary={summary} />
      <EvidenceCompletenessCard summary={summary} />
      <PendingActionsCard summary={summary} basePath={basePath} />
      <ReportTimelineCard summary={summary} />
    </div>
  )
}
