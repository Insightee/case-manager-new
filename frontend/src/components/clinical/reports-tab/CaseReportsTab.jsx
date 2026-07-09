import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../../../styles/case-reports-tab.css'
import { useCaseReportsSummary } from '../../../hooks/useCaseReportsSummary.js'
import {
  filterHistory,
  monthOptionsFromHistory,
  navigateToReport,
  yearOptionsFromFilters,
} from '../../../lib/caseReportsCompose.js'
import { CaseReportsHeader } from './CaseReportsHeader.jsx'
import { NeedsAttentionList } from './NeedsAttentionList.jsx'
import { CurrentReportLifecycleStrip } from './CurrentReportLifecycleStrip.jsx'
import { WorkingProgressCard } from './WorkingProgressCard.jsx'
import { ReportFilters } from './ReportFilters.jsx'
import { ReportHistoryTimeline } from './ReportHistoryTimeline.jsx'

const EMPTY_PROGRESS_CARDS = [
  {
    type: 'observation_report',
    icon: 'visibility',
    title: 'Observation Report',
    body: 'Log real-time observations and behavioral cues during sessions.',
  },
  {
    type: 'monthly_report',
    icon: 'calendar_month',
    title: 'Monthly Progress',
    body: 'Summarize month-over-month growth and objective metrics.',
  },
]

export function CaseReportsTab({ caseId, variant = 'therapist' }) {
  const navigate = useNavigate()
  const { data: summary, isLoading, isError, error, refetch } = useCaseReportsSummary(caseId)
  const [filters, setFilters] = useState({
    search: '',
    month: 'all',
    year: 'all',
    type: 'all',
    status: 'all',
  })
  const [showAllAttention, setShowAllAttention] = useState(false)

  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`

  const handleAction = (item) => {
    const url = item?.target_url
    if (url) {
      navigateToReport(navigate, url)
      return
    }
    navigate(`${basePath}?tab=reports`)
  }

  const handleCreateType = (type) => {
    const action = (summary?.create_actions || []).find((a) => a.type === type)
    if (action) handleAction(action)
  }

  const filteredHistory = useMemo(
    () => filterHistory(summary?.history || [], filters),
    [summary?.history, filters],
  )

  const monthOptions = useMemo(
    () => monthOptionsFromHistory(summary?.history || []),
    [summary?.history],
  )
  const yearOptions = useMemo(
    () => yearOptionsFromFilters(summary?.filters),
    [summary?.filters],
  )

  const attentionItems = showAllAttention
    ? summary?.attention_items || []
    : (summary?.attention_items || []).slice(0, 5)

  if (isLoading) {
    return <p className="crt-page forest-light crt-loading-note">Loading report history for this case…</p>
  }

  if (isError) {
    return (
      <div className="crt-page forest-light crt-empty-note">
        <p>{error?.message || 'Could not load reports for this case.'}</p>
        <button type="button" className="crt-link-btn" onClick={() => refetch()}>
          Try again
        </button>
      </div>
    )
  }

  if (summary?.is_empty) {
    const childName = summary.client?.name || 'this child'
    const firstCreate = summary.create_actions?.[0]
    return (
      <div className="crt-page forest-light crt-empty">
        <CaseReportsHeader createActions={summary.create_actions} onCreate={handleAction} />
        <div className="crt-empty__canvas">
          <div className="crt-empty__art" aria-hidden="true">
            <div className="crt-empty__art-glow" />
            <div className="crt-empty__art-card crt-empty__art-card--back">
              <span className="material-symbols-outlined">description</span>
            </div>
            <div className="crt-empty__art-card crt-empty__art-card--front">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
                description
              </span>
            </div>
            <div className="crt-empty__art-badge">
              <span className="material-symbols-outlined">edit_note</span>
            </div>
          </div>
          <h2 className="crt-empty__title">No reports created yet.</h2>
          <p className="crt-empty__body">
            Start your first Observation Report or add a Monthly Report to begin tracking progress for{' '}
            {childName}&apos;s case.
          </p>
          <div className="crt-empty__actions">
            <button
              type="button"
              className="crt-empty__cta"
              onClick={() => firstCreate && handleAction(firstCreate)}
            >
              <span className="material-symbols-outlined" aria-hidden="true">post_add</span>
              Create First Report
            </button>
          </div>
          <div className="crt-empty__progress-cards">
            {EMPTY_PROGRESS_CARDS.map((card) => (
              <button
                key={card.type}
                type="button"
                className="crt-progress-card"
                onClick={() => handleCreateType(card.type)}
              >
                <div className="crt-progress-card__icon">
                  <span className="material-symbols-outlined" aria-hidden="true">{card.icon}</span>
                </div>
                <h3 className="crt-progress-card__title">{card.title}</h3>
                <p className="crt-progress-card__body">{card.body}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="crt-page forest-light">
      <CaseReportsHeader createActions={summary.create_actions} onCreate={handleAction} />

      <NeedsAttentionList
        items={attentionItems}
        hasMore={!showAllAttention && summary.has_more_attention}
        onAction={handleAction}
        onViewAll={() => setShowAllAttention(true)}
      />

      <WorkingProgressCard workingProgress={summary.working_progress} onAction={handleAction} />

      <CurrentReportLifecycleStrip items={summary.current_status} onAction={handleAction} />

      <ReportFilters
        filters={filters}
        onChange={setFilters}
        monthOptions={monthOptions}
        yearOptions={yearOptions}
      />

      <ReportHistoryTimeline groups={filteredHistory} onAction={handleAction} />
    </div>
  )
}
