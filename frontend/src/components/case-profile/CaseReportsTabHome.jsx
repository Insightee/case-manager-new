import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { CaseReportTypeCard } from './CaseReportTypeCard.jsx'
import { ReportsSectionHeader, ReportsMetricCard, ReportsMetricGrid } from '../reports-hub/index.js'

function normStatus(value) {
  return String(value || '').toLowerCase().replace(/\s+/g, '_')
}

function computePipelineCounts(reports, summary) {
  const clientMonthly = (reports || []).filter((r) => normStatus(r.category) !== 'progress')
  const draft = clientMonthly.filter((r) => ['draft', 'rejected'].includes(normStatus(r.status))).length
  const underReview = clientMonthly.filter((r) => normStatus(r.status) === 'under_review').length
  const published = clientMonthly.filter((r) => normStatus(r.status) === 'published').length
  const missingCurrent = summary?.missing_items?.includes('monthly_report_current_month') ? 1 : 0
  const rejected = summary?.report_statuses?.rejected_count || 0
  const attentionItems = (summary?.recommended_next_actions || []).length
  const overdue = missingCurrent + rejected + (summary?.risk_level === 'urgent' ? 1 : 0)
  return {
    draft,
    underReview,
    published,
    overdue: overdue || (attentionItems > 2 ? 1 : 0),
  }
}

function formatStatusLabel(status) {
  if (!status) return 'Not started'
  return String(status).replace(/_/g, ' ')
}

function currentMonthLabel() {
  return new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
}

function sectionForCard(cardId) {
  if (cardId === 'drive') return 'documents'
  return cardId
}

export function CaseReportsTabHome({ caseId, childName, onOpenSection }) {
  const [workbench, setWorkbench] = useState(null)
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [wb, qs] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}/reports-workbench`),
        apiFetch(`/api/v1/cases/${caseId}/clinical-quality-summary`),
      ])
      setWorkbench(wb)
      setSummary(qs)
    } catch (err) {
      setError(err.message || 'Could not load reports overview.')
      setWorkbench(null)
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const pipeline = useMemo(
    () => computePipelineCounts(workbench?.monthly_reports, summary),
    [workbench, summary],
  )

  const reportCards = useMemo(() => {
    const obs = workbench?.observation
    const obsStatus = obs?.status || summary?.report_statuses?.observation_status
    const iepStatus = workbench?.iep_plan_status || summary?.report_statuses?.iep_status
    const currentMonth = summary?.report_statuses?.current_month || currentMonthLabel()
    const currentMonthStatus = summary?.report_statuses?.current_month_status
    const progressReports = (workbench?.monthly_reports || []).filter(
      (r) => normStatus(r.category) === 'progress',
    )
    const latestProgress = progressReports[0]

    const missing = summary?.missing_items || []
    const recommended = summary?.recommended_next_actions || []

    return [
      {
        id: 'observation',
        title: 'Observation Report',
        subtitle: 'Initial strengths, environment, and support needs',
        status: obsStatus,
        statusLabel: formatStatusLabel(obsStatus),
        alert: missing.includes('observation_checklist')
          ? 'Observation checklist still needs completion before goals can graduate.'
          : obs?.is_overdue
            ? 'Observation report is overdue — finish or revise to keep the pipeline moving.'
            : null,
        meta: obs?.is_overdue ? 'Overdue checklist' : 'Initial assessment',
        ctaLabel: obsStatus ? 'Continue observation' : 'Start observation',
      },
      {
        id: 'iep',
        title: 'IEP Support Plan',
        subtitle: 'Goals, strategies, and measurement framework',
        status: iepStatus,
        statusLabel: summary?.report_statuses?.has_active_iep ? 'Active IEP' : formatStatusLabel(iepStatus),
        alert: missing.includes('active_iep')
          ? 'An active IEP unlocks goal tracking and monthly report baselines.'
          : null,
        meta: 'Support plan',
        ctaLabel: summary?.report_statuses?.has_active_iep ? 'Open IEP' : 'Build IEP',
      },
      {
        id: 'monthly',
        title: 'Monthly Report',
        subtitle: `${currentMonth} client progress`,
        status: currentMonthStatus,
        statusLabel: currentMonthStatus ? formatStatusLabel(currentMonthStatus) : 'No draft yet',
        alert: missing.includes('monthly_report_current_month')
          ? `No monthly draft for ${currentMonth} yet — generate from session logs when ready.`
          : recommended.find((a) => a.toLowerCase().includes('monthly')) || null,
        meta: currentMonth,
        ctaLabel: currentMonthStatus ? 'Open monthly report' : 'Create monthly draft',
      },
      {
        id: 'progress',
        title: 'Progress Report',
        subtitle: 'Longitudinal trends across monthly reports',
        status: latestProgress?.status,
        statusLabel: latestProgress ? formatStatusLabel(latestProgress.status) : 'As needed',
        alert: null,
        meta: latestProgress?.month ? `Latest · ${latestProgress.month}` : 'Periodic summary',
        ctaLabel: latestProgress ? 'Open progress report' : 'View progress reports',
      },
      {
        id: 'drive',
        title: 'Document Drive',
        subtitle: 'Evidence uploads and shared clinical files',
        status: 'available',
        statusLabel: 'Evidence hub',
        progress: summary?.evidence_summary?.total_evidence_events
          ? Math.min(100, 20 + summary.evidence_summary.total_evidence_events * 8)
          : 20,
        alert: (summary?.evidence_summary?.sessions_without_goal_entries || 0) > 0
          ? `${summary.evidence_summary.sessions_without_goal_entries} recent sessions still need structured goal evidence.`
          : null,
        meta: `${summary?.evidence_summary?.total_evidence_events || 0} evidence events`,
        ctaLabel: 'Open document drive',
      },
    ]
  }, [workbench, summary])

  if (loading) {
    return <p className="ic-case-panel__loading">Loading reports overview…</p>
  }

  if (error) {
    return <p className="ic-case-panel__error">{error}</p>
  }

  return (
    <div className="cp-reports-tab-home">
      <ReportsSectionHeader
        title="Reports Dashboard"
        subtitle={`Monitor and manage clinical documentation for ${childName}.`}
        action={(
          <button
            type="button"
            className="reports-hub-btn reports-hub-btn--primary"
            onClick={() => onOpenSection('monthly')}
          >
            + Create New Draft
          </button>
        )}
      />

      <ReportsMetricGrid className="cp-reports-tab-home__metrics">
        <ReportsMetricCard
          label="Active Drafts"
          value={pipeline.draft}
          tone="draft"
          onClick={() => onOpenSection('monthly')}
        />
        <ReportsMetricCard
          label="Pending Review"
          value={pipeline.underReview}
          tone="underReview"
          onClick={() => onOpenSection('monthly')}
        />
        <ReportsMetricCard
          label="Approved"
          value={pipeline.published}
          tone="published"
          onClick={() => onOpenSection('monthly')}
        />
        <ReportsMetricCard
          label="Needs Attention"
          value={pipeline.overdue}
          tone="overdue"
          onClick={() => onOpenSection('monthly')}
        />
      </ReportsMetricGrid>

      {summary?.recommended_next_actions?.length ? (
        <div className="cp-reports-tab-home__actions" role="status">
          <p className="cp-reports-tab-home__actions-label">Suggested next steps</p>
          <ul>
            {summary.recommended_next_actions.slice(0, 4).map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <section className="cp-reports-tab-home__pipeline" aria-label="Report types">
        <h3 className="cp-reports-tab-home__pipeline-title">Active reports</h3>
        <div className="cp-reports-tab-home__pipeline-grid">
          {reportCards.map((card) => (
            <CaseReportTypeCard
              key={card.id}
              {...card}
              onOpen={() => onOpenSection(sectionForCard(card.id))}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
