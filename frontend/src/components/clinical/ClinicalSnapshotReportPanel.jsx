import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { currentMonthValue, SNAPSHOT_STATUS_LABELS } from '../../lib/insightsConstants.js'
import { ClinicalPrimaryButton } from '../clinical-ui/ClinicalPrimaryButton.jsx'
import { ClinicalSecondaryButton } from '../clinical-ui/ClinicalSecondaryButton.jsx'

export function ClinicalSnapshotReportPanel({ caseId, reportId, month }) {
  const navigate = useNavigate()
  const [snapshots, setSnapshots] = useState([])
  const [loading, setLoading] = useState(true)
  const selectedMonth = month || currentMonthValue()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/insights/snapshots?month=${selectedMonth}`)
      setSnapshots(data.items || [])
    } catch {
      setSnapshots([])
    } finally {
      setLoading(false)
    }
  }, [caseId, selectedMonth])

  useEffect(() => { load() }, [load])

  const snapshot = snapshots[0]

  const insertSection = async (section) => {
    if (!snapshot?.id || !reportId) return
    await apiFetch(`/api/v1/reports/monthly/${reportId}/insights/insert-snapshot-section`, {
      method: 'POST',
      body: JSON.stringify({ snapshot_id: snapshot.id, section }),
    })
  }

  if (loading) return <p className="ic-case-panel__loading">Loading clinical snapshot…</p>

  if (!snapshot) {
    return (
      <div className="insights-report-panel">
        <h4>Use Clinical Snapshot</h4>
        <p>No snapshot generated for this month.</p>
        <ClinicalPrimaryButton onClick={() => navigate(`/therapist/cases/${caseId}?tab=insights`)}>
          Generate Clinical Snapshot
        </ClinicalPrimaryButton>
      </div>
    )
  }

  return (
    <div className="insights-report-panel">
      <h4>Use Clinical Snapshot</h4>
      <p>
        {selectedMonth} snapshot available — Status: {SNAPSHOT_STATUS_LABELS[snapshot.status] || snapshot.status}
      </p>
      <div className="insights-snapshot-actions">
        <ClinicalSecondaryButton onClick={() => insertSection('goal_summary')}>Insert goal summary</ClinicalSecondaryButton>
        <ClinicalSecondaryButton onClick={() => insertSection('parent_safe_summary')}>Insert parent-safe draft</ClinicalSecondaryButton>
        <ClinicalSecondaryButton onClick={() => navigate(`/therapist/cases/${caseId}?tab=insights`)}>View snapshot</ClinicalSecondaryButton>
        <ClinicalSecondaryButton onClick={() => apiFetch(`/api/v1/cases/${caseId}/insights/snapshots/${snapshot.id}/send-review`, { method: 'POST' }).then(load)}>
          Send to CM review
        </ClinicalSecondaryButton>
      </div>
      {snapshot.status !== 'approved' ? (
        <p className="insights-ai-hint">AI-assisted draft. Requires review before parent-facing use.</p>
      ) : null}
    </div>
  )
}
