import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../../lib/apiClient.js'
import { ClinicalQualitySummary } from '../quality/ClinicalQualitySummary.jsx'
import { GoalQualityReviewPanel } from './GoalQualityReviewPanel.jsx'
import { StrategyCandidateReviewPanel } from './StrategyCandidateReviewPanel.jsx'
import { ReportReviewReadinessPanel } from './ReportReviewReadinessPanel.jsx'

export function CaseManagerSupervisionPanel({ caseId, caseCode }) {
  const [summary, setSummary] = useState(null)

  const load = useCallback(async () => {
    try {
      const [data, queue] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}/clinical-quality-summary`),
        apiFetch(`/api/v1/cases/${caseId}/repository-review-queue`).catch(() => null),
      ])
      if (queue?.goals?.length || queue?.strategies?.length) {
        setSummary({
          ...data,
          custom_items_pending_review: {
            goals: queue.goals || data?.custom_items_pending_review?.goals || [],
            strategies: queue.strategies || data?.custom_items_pending_review?.strategies || [],
          },
        })
      } else {
        setSummary(data)
      }
    } catch {
      setSummary(null)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="cp-cm-supervision">
      <p className="ic-reports-flow__intro">
        Case manager supervision view — documentation risk, repository queue, and report readiness.
      </p>
      <ClinicalQualitySummary caseId={caseId} variant="admin" />
      <ReportReviewReadinessPanel summary={summary} caseId={caseId} />
      <GoalQualityReviewPanel caseId={caseId} pending={summary?.custom_items_pending_review?.goals || []} onUpdated={load} />
      <StrategyCandidateReviewPanel caseId={caseId} pending={summary?.custom_items_pending_review?.strategies || []} onUpdated={load} />
      {caseCode ? (
        <Link to={`/admin/reports?case_id=${caseId}`} className="ic-btn ic-btn--ghost ic-btn--sm">
          Open reports queue
        </Link>
      ) : null}
    </div>
  )
}
