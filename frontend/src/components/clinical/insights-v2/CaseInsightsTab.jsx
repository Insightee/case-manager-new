import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../../../styles/case-insights-v2.css'
import { useCaseInsights } from '../../../hooks/useCaseInsights.js'
import { ChildSnapshotSection } from './ChildSnapshotSection.jsx'
import { IepGoalProgressSection } from './IepGoalProgressSection.jsx'
import { NextSessionFocusCard } from './NextSessionFocusCard.jsx'
import { CollaborativeInputsGrid } from './CollaborativeInputsGrid.jsx'
import { SessionLogInsightsSection } from './SessionLogInsightsSection.jsx'
import { SuggestedGoalsStrategiesSection } from './SuggestedGoalsStrategiesSection.jsx'
import { InsightsBottomActions } from './InsightsBottomActions.jsx'
import { InsightsRefreshBar } from './InsightsRefreshBar.jsx'

export function CaseInsightsTab({ caseId, variant = 'therapist' }) {
  const navigate = useNavigate()
  const {
    summary,
    isLoading,
    isError,
    usage,
    insights,
    insightsById,
    selectedIds,
    toggleSelected,
    refresh,
    isRefreshing,
    refreshMessage,
    submitSelected,
    isSubmittingSelection,
  } = useCaseInsights(caseId)

  const [stagedMessage, setStagedMessage] = useState('')

  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`

  const childSnapshotInsight = insightsById.get('child_snapshot')
  const nextSessionInsight = insightsById.get('next_session_focus')

  const handleSubmit = async (destination) => {
    try {
      await submitSelected(destination)
      setStagedMessage(
        destination === 'monthly_report'
          ? 'Added selected insights to the monthly report queue for review.'
          : 'Submitted selected items for IEP review.',
      )
      window.setTimeout(() => setStagedMessage(''), 4000)
    } catch (err) {
      setStagedMessage(err?.message || 'Could not save selection. Try again.')
    }
  }

  const selectedCount = selectedIds.size

  const goalCount = summary?.activeIEP?.goals?.length || 0

  if (isLoading) {
    return (
      <div className="ci-page forest-light">
        <p className="ci-loading-note">Loading insights from session logs and IEP goals…</p>
      </div>
    )
  }

  if (isError || !summary) {
    return (
      <div className="ci-page forest-light">
        <p className="ci-empty-note">
          Looks like we still need a few details before insights can be shown. Try refreshing the page.
        </p>
      </div>
    )
  }

  return (
    <div className="ci-page forest-light">
      <InsightsRefreshBar usage={usage} onRefresh={refresh} isRefreshing={isRefreshing} message={refreshMessage} />

      <ChildSnapshotSection
        child={summary.child}
        insight={childSnapshotInsight}
        selected={selectedIds.has('child_snapshot')}
        onToggleSelect={toggleSelected}
      />

      <IepGoalProgressSection
        goals={summary.activeIEP?.goals}
        insightsById={insightsById}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelected}
        onViewFullIep={() => navigate(`${basePath}?tab=goals`)}
        onViewEvidence={() => navigate(variant === 'admin' ? `${basePath}?tab=logs` : '/therapist/logs')}
      />

      <NextSessionFocusCard
        focus={summary.nextSessionFocus}
        insight={nextSessionInsight}
        selected={selectedIds.has('next_session_focus')}
        onToggleSelect={toggleSelected}
      />

      <CollaborativeInputsGrid
        cards={summary.collaborativeInputs}
        insightsById={insightsById}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelected}
      />

      <SessionLogInsightsSection
        evidence={summary.evidence}
        insightsById={insightsById}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelected}
      />

      <SuggestedGoalsStrategiesSection suggested={summary.suggested} />

      {stagedMessage ? <p className="ci-staged-message" role="status">{stagedMessage}</p> : null}

      <InsightsBottomActions
        selectedCount={selectedCount}
        onAddToMonthlyReport={() => handleSubmit('monthly_report')}
        onSubmitForIepReview={() => handleSubmit('iep_review')}
        busy={isSubmittingSelection}
      />

      {goalCount === 0 && insights.length <= 1 ? (
        <p className="ci-empty-note">
          Add IEP goals and session logs for this case to start building structured insights.
        </p>
      ) : null}
    </div>
  )
}
