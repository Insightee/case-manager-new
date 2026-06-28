import { Link, useNavigate } from 'react-router-dom'
import { ClinicalCard } from '../../clinical-ui/ClinicalCard.jsx'
import { ClinicalMetricCard } from '../../clinical-ui/ClinicalMetricCard.jsx'
import { ClinicalProgressBar } from '../../clinical-ui/ClinicalProgressBar.jsx'
import { ClinicalGuidanceCard } from '../../clinical-ui/ClinicalGuidanceCard.jsx'
import { ClinicalEmptyState } from '../../clinical-ui/ClinicalEmptyState.jsx'
import { ClinicalStatusBadge } from '../../clinical-ui/ClinicalStatusBadge.jsx'

import { CaseSummaryEditor } from './CaseSummaryEditor.jsx'

function iepHealthMetric(summary) {
  const status = summary?.documentation_status
  if (status === 'complete') return { label: 'Stable', tone: 'success' }
  if (status === 'needs_revision') return { label: 'Needs review', tone: 'attention' }
  return { label: 'In progress', tone: 'default' }
}

function pendingReportCount(rs) {
  let count = (rs.pending_review_count || 0) + (rs.rejected_count || 0)
  if (rs.current_month_status === 'draft') count += 1
  if (!rs.current_month_status && rs.current_month) count += 1
  return count
}

function goalProgressPct(sessionsAddressed) {
  return Math.min(100, Math.round(((sessionsAddressed || 0) / 4) * 100))
}

function buildReportActivity(summary) {
  return (summary?.report_timeline || []).slice(0, 6).map((row) => ({
    id: `${row.type}-${row.id}`,
    month: row.month,
    status: row.status,
    reportId: row.id,
  }))
}

function buildStakeholders(caseRow) {
  const rows = []
  rows.push({
    key: 'parent',
    name: caseRow?.parent_name || 'Primary caregiver',
    role: 'Parent',
  })
  if (caseRow?.case_manager_name) {
    rows.push({ key: 'cm', name: caseRow.case_manager_name, role: 'Case manager' })
  }
  if (caseRow?.therapist_name) {
    rows.push({ key: 'therapist', name: caseRow.therapist_name, role: 'Therapist' })
  }
  return rows
}

function guidanceFromSummary(summary, scheduleItems) {
  const action = summary?.recommended_next_actions?.[0]
  const next = scheduleItems?.find((s) => s.status !== 'COMPLETED') || scheduleItems?.[0]
  const nextLine = next
    ? `Next session: ${next.date || next.scheduled_date || 'TBD'}${next.startTime || next.start_time ? ` · ${next.startTime || next.start_time}` : ''}.`
    : null

  if (action) {
    return { variant: 'guidance', title: 'Suggested next step', body: [action, nextLine].filter(Boolean).join(' ') }
  }
  if (summary?.documentation_status === 'complete') {
    return {
      variant: 'success',
      title: 'Documentation on track',
      body: [nextLine, 'Session evidence and reports are flowing. Review insights for patterns across goals.'].filter(Boolean).join(' '),
    }
  }
  return {
    variant: 'guidance',
    title: 'Review case signals',
    body: [nextLine, 'Open Insights to see goal coverage and documentation status for this case.'].filter(Boolean).join(' '),
  }
}

function ReportActivityList({ items, basePath, onViewAll }) {
  if (!items.length) return null

  return (
    <div className="clinical-report-activity">
      <ul className="clinical-report-activity__list">
        {items.map((item) => (
          <li key={item.id} className="clinical-report-activity__item">
            <div className="clinical-report-activity__leading" aria-hidden="true">
              <span className="clinical-report-activity__doc-icon" />
            </div>
            <div className="clinical-report-activity__main">
              <p className="clinical-report-activity__month">{item.month || '—'}</p>
              <p className="clinical-report-activity__type">Monthly report</p>
            </div>
            <div className="clinical-report-activity__status">
              <ClinicalStatusBadge status={item.status} />
            </div>
            <Link
              to={`${basePath}?tab=reports`}
              className="clinical-report-activity__link"
            >
              Open
            </Link>
          </li>
        ))}
      </ul>
      {onViewAll ? (
        <button type="button" className="clinical-text-action clinical-report-activity__view-all" onClick={onViewAll}>
          View all reports
        </button>
      ) : null}
    </div>
  )
}

export function TherapistCaseOverviewDashboard({
  caseId,
  caseRow,
  clinicalProfile,
  scheduleItems,
  qualitySummary,
  onOpenTab,
  onClinicalProfileUpdated,
}) {
  const navigate = useNavigate()
  const basePath = `/therapist/cases/${caseId}`
  const goals = qualitySummary?.goal_coverage || []
  const evidenceCount = qualitySummary?.evidence_summary?.total_evidence_events ?? 0
  const pendingReports = pendingReportCount(qualitySummary?.report_statuses || {})
  const iepHealth = iepHealthMetric(qualitySummary || {})
  const reportActivity = buildReportActivity(qualitySummary || {})
  const stakeholders = buildStakeholders(caseRow)
  const guidance = guidanceFromSummary(qualitySummary || {}, scheduleItems)

  return (
    <div className="cp-therapist-overview clinical-overview">
      <CaseSummaryEditor
        caseId={caseId}
        clinicalProfile={clinicalProfile}
        onProfileUpdated={onClinicalProfileUpdated}
      />

      <div className="clinical-metric-grid">
        <ClinicalMetricCard
          value={evidenceCount}
          label="Evidence events"
          icon="evidence"
          onClick={() => onOpenTab('documents')}
        />
        <ClinicalMetricCard
          value={goals.length}
          label="Active goals"
          icon="goals"
          onClick={() => onOpenTab('goals')}
        />
        <ClinicalMetricCard
          value={pendingReports}
          label="Pending reports"
          icon="reports"
          valueTone={pendingReports > 0 ? 'attention' : 'default'}
          onClick={() => onOpenTab('reports')}
        />
        <ClinicalMetricCard
          value={iepHealth.label}
          label="Documentation"
          icon="documentation"
          valueTone={iepHealth.tone}
          onClick={() => onOpenTab('insights')}
        />
      </div>

      <div className="clinical-two-col">
        <div className="clinical-overview-main">
          <section className="clinical-overview-section" aria-labelledby="active-goals-heading">
            <div className="clinical-overview-section__head">
              <h3 id="active-goals-heading" className="clinical-overview-section__title">
                Active goals progress
              </h3>
              {goals.length ? (
                <Link to={`${basePath}?tab=goals`} className="clinical-text-action">
                  View all
                </Link>
              ) : null}
            </div>
            {goals.length ? (
              <div className="clinical-overview-goal-grid">
                {goals.slice(0, 4).map((goal) => {
                  const pct = goalProgressPct(goal.sessions_addressed)
                  const variant = goal.stale ? 'amber' : pct >= 70 ? 'green' : 'default'
                  return (
                    <article
                      key={goal.label}
                      className={`clinical-overview-goal-card${goal.stale ? ' is-stale' : ''}`}
                    >
                      <ClinicalProgressBar label={goal.label} pct={pct} variant={variant} showPct />
                      <p className="clinical-overview-goal-card__meta">
                        {goal.sessions_addressed ?? 0} session(s) with evidence
                        {goal.stale ? ' · Needs fresh evidence' : ' · On track'}
                      </p>
                    </article>
                  )
                })}
              </div>
            ) : (
              <ClinicalEmptyState
                title="No active goals yet"
                body="Goals appear once an active IEP is in place."
                actionLabel="Open IEP"
                actionHref={`${basePath}?tab=reports&section=iep`}
              />
            )}
          </section>

          <ClinicalCard title="Recent activity">
            {reportActivity.length ? (
              <ReportActivityList
                items={reportActivity}
                basePath={basePath}
                onViewAll={() => onOpenTab('reports')}
              />
            ) : (
              <ClinicalEmptyState
                title="No recent report activity"
                body="Monthly reports and observation milestones will appear here."
                actionLabel="Open reports"
                onAction={() => onOpenTab('reports')}
              />
            )}
          </ClinicalCard>
        </div>

        <aside className="clinical-overview-side">
          <ClinicalGuidanceCard
            variant={guidance.variant}
            title={guidance.title}
            body={guidance.body}
            actionLabel="Open insights →"
            onAction={() => onOpenTab('insights')}
          />

          <ClinicalCard title="Stakeholders">
            <ul className="clinical-overview-stakeholders">
              {stakeholders.map((person) => (
                <li key={person.key} className="clinical-overview-stakeholder">
                  <span className="clinical-overview-stakeholder__avatar" aria-hidden="true">
                    {person.name.slice(0, 2).toUpperCase()}
                  </span>
                  <div className="clinical-overview-stakeholder__info">
                    <p className="clinical-overview-stakeholder__name">{person.name}</p>
                    <p className="clinical-overview-stakeholder__role">{person.role}</p>
                  </div>
                </li>
              ))}
            </ul>
          </ClinicalCard>

          <ClinicalCard title="Quick actions">
            <div className="clinical-overview-quick-actions">
              <button
                type="button"
                className="clinical-overview-quick-action"
                onClick={() => navigate('/therapist/logs')}
              >
                <span className="clinical-overview-quick-action__icon clinical-overview-quick-action__icon--logs" aria-hidden="true" />
                <span>Open session logs</span>
              </button>
              <button type="button" className="clinical-overview-quick-action" onClick={() => onOpenTab('reports')}>
                <span className="clinical-overview-quick-action__icon clinical-overview-quick-action__icon--reports" aria-hidden="true" />
                <span>Open reports</span>
              </button>
              <button type="button" className="clinical-overview-quick-action" onClick={() => onOpenTab('documents')}>
                <span className="clinical-overview-quick-action__icon clinical-overview-quick-action__icon--upload" aria-hidden="true" />
                <span>Upload evidence</span>
              </button>
            </div>
          </ClinicalCard>
        </aside>
      </div>
    </div>
  )
}
