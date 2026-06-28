import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { StudentGoalCreateModal } from '../../clinical/goals-strategy/StudentGoalCreateModal.jsx'
import { StitchWorkspaceSubhead } from '../observation/stitch/ObservationStitchBlocks.jsx'
import { useIepReport } from '../hooks/useIepReport.js'
import { ClinicalBuilderShell } from '../shared/ClinicalBuilderShell.jsx'
import { IepApprovalPanel } from './IepApprovalPanel.jsx'
import { IepGoalEditor } from './IepGoalCard.jsx'
import { IepBuilderSections } from './IepBuilderSections.jsx'
import { IepReviewSuggestionsPanel } from './IepReviewSuggestionsPanel.jsx'
import { IepInsightsRail } from './IepInsightsRail.jsx'
import { IepPendingChangesPanel } from './IepPendingChangesPanel.jsx'

function sectionData(sections, key) {
  return sections?.find((s) => s.key === key) || {}
}

export function IepBuilderPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const navigate = useNavigate()
  const basePath = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`
  const isAdmin = variant === 'admin'

  const {
    workspace,
    availableGoals,
    summary,
    suggestions,
    pendingChanges,
    loading,
    error,
    saving,
    loadWorkspace,
    generateFromObservation,
    patchSection,
    patchClinicalInsights,
    addGoal,
    patchGoal,
    deleteGoal,
    markAchieved,
    submitReport,
    saveDraft,
    approveChanges,
    returnChanges,
    generateSuggestions,
    sendForStakeholderApproval,
    stakeholderApprove,
    stakeholderRequestReview,
    cmResendForApproval,
    AUTO_SAVE_MS,
  } = useIepReport(caseId)

  const [goalModal, setGoalModal] = useState(false)
  const [strategyGoal, setStrategyGoal] = useState(null)
  const [editGoal, setEditGoal] = useState(null)
  const [insightsOpen, setInsightsOpen] = useState(false)
  const [generatingInsights, setGeneratingInsights] = useState(false)
  const [approvalBusy, setApprovalBusy] = useState(false)
  const importedFromObs = useRef(false)

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  useEffect(() => {
    if (!workspace?.can_edit || !workspace?.report_id) return undefined
    const t = window.setInterval(() => saveDraft(), AUTO_SAVE_MS)
    return () => window.clearInterval(t)
  }, [workspace?.can_edit, workspace?.report_id, saveDraft, AUTO_SAVE_MS])

  const readOnly = !workspace?.can_edit
  const sections = workspace?.sections || []
  const goalsPlan = sectionData(sections, 'goals_plan').structured_data || {}
  const goals = goalsPlan.goals || []
  const clinicalInsights = sectionData(sections, 'clinical_insights').structured_data || {}

  useEffect(() => {
    if (importedFromObs.current || loading || !workspace?.report_id || readOnly) return
    if (goals.length > 0 || !summary?.observation_approved) return
    importedFromObs.current = true
    generateFromObservation().catch(() => {
      importedFromObs.current = false
    })
  }, [loading, workspace?.report_id, goals.length, readOnly, summary?.observation_approved, generateFromObservation])

  const suggestedGoals = useMemo(() => {
    if (!availableGoals) return []
    const items = []
    for (const g of availableGoals.observation_candidates || []) items.push({ ...g, _source: 'observation' })
    for (const g of availableGoals.session_log_goals || []) items.push({ ...g, _source: 'session_log' })
    for (const g of availableGoals.case_goals || []) items.push({ ...g, _source: 'repository' })
    for (const g of availableGoals.active_iep_cards || []) {
      items.push({ ...g, label: g.label || g.goal_statement, _source: 'iep' })
    }
    return items
  }, [availableGoals])

  const handleImportSuggestedGoal = useCallback(
    async (candidate) => {
      if (!workspace?.report_id) return
      try {
        if (candidate.id && candidate._source === 'observation') {
          await addGoal({
            goal_source_id: candidate.id,
            source_type: 'observation_candidate',
            title: candidate.label,
            goal_statement: candidate.goal_statement || candidate.label,
            domain: candidate.domain_key || 'general',
          })
        } else {
          await addGoal({
            title: candidate.label,
            goal_statement: candidate.goal_statement || candidate.label,
            domain: candidate.domain_key || 'general',
            baseline_current_state: candidate.baseline_state || candidate.baseline_note || '',
            desired_state: candidate.desired_state || candidate.desired_direction || '',
          })
        }
        await loadWorkspace()
      } catch {
        /* hook surfaces error */
      }
    },
    [workspace?.report_id, addGoal, loadWorkspace],
  )

  const handleGenerateInsights = useCallback(async () => {
    setGeneratingInsights(true)
    try {
      await generateSuggestions()
    } finally {
      setGeneratingInsights(false)
    }
  }, [generateSuggestions])

  const statusLabel = (workspace?.status || 'draft').replace(/_/g, ' ').toUpperCase()
  const reviewPlan = sectionData(sections, 'review_parent_plan').structured_data || {}
  const aggregatedInputs = workspace?.aggregated_inputs || suggestions?.aggregated_inputs || null

  const importTherapistInput = useCallback(
    (text) => {
      if (!text?.trim()) return
      const existing = (reviewPlan.therapist_input || '').trim()
      patchSection('review_parent_plan', {
        structured_data: {
          ...reviewPlan,
          therapist_input: existing ? `${existing}\n\n${text.trim()}` : text.trim(),
        },
      })
    },
    [reviewPlan, patchSection],
  )

  const importParentInput = useCallback(
    (text) => {
      if (!text?.trim()) return
      const existing = (reviewPlan.parent_input_draft || '').trim()
      patchSection('review_parent_plan', {
        structured_data: {
          ...reviewPlan,
          parent_input_draft: existing ? `${existing}\n\n${text.trim()}` : text.trim(),
        },
      })
    },
    [reviewPlan, patchSection],
  )

  const goPreview = useCallback(() => {
    navigate(`${basePath}?tab=reports&section=iep&view=preview`)
  }, [navigate, basePath])

  if (loading && !workspace) {
    return <p className="text-sm text-on-surface-variant clinical-report-ui">Loading IEP builder…</p>
  }

  return (
    <div className="iep-workspace clinical-report-ui forest-light pb-24">
      <StitchWorkspaceSubhead
        caseCode={caseCode}
        saving={saving}
        title="IEP Report Builder"
        aiAssistantOpen={insightsOpen}
        onToggleAiAssistant={() => {
          setInsightsOpen((open) => {
            const next = !open
            // #region agent log
            fetch('http://127.0.0.1:7284/ingest/6bb4b18a-59b3-4583-8388-f541aa2607d1', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '3264f0' },
              body: JSON.stringify({
                sessionId: '3264f0',
                location: 'IepBuilderPage.jsx:toggleAi',
                message: 'InsighteAI panel toggled',
                data: { open: next },
                hypothesisId: 'H3',
                timestamp: Date.now(),
              }),
            }).catch(() => {})
            // #endregion
            return next
          })
        }}
        completionPct={workspace?.completion_pct ?? 0}
      />

      {insightsOpen ? (
        <IepInsightsRail
          open={insightsOpen}
          insights={suggestions}
          clinicalInsights={clinicalInsights}
          aggregatedInputs={aggregatedInputs}
          readOnly={readOnly}
          generating={generatingInsights}
          onGenerate={handleGenerateInsights}
          onPatchInsights={patchClinicalInsights}
          onImportTherapistInput={importTherapistInput}
          onImportParentInput={importParentInput}
        />
      ) : null}

      <div className="flex flex-col">
        <div className="flex-1 min-w-0">
          <ClinicalBuilderShell
            title="IEP Support Plan"
            statusLabel={statusLabel}
            saving={saving}
            readOnly={readOnly}
            canSubmit={workspace?.can_submit}
            onSaveDraft={saveDraft}
            onPreview={goPreview}
            onSubmit={submitReport}
            onAddGoal={() => {
              setStrategyGoal(null)
              setGoalModal(true)
            }}
          >
            {error ? (
              <p className="mb-4 px-4 py-3 rounded-lg bg-error-container text-on-error-container text-sm" role="alert">
                {error}
              </p>
            ) : null}

            <IepApprovalPanel
              approval={workspace?.iep_approval}
              reviewThread={workspace?.review_thread}
              variant={variant}
              readOnly={readOnly}
              busy={approvalBusy}
              onSendForStakeholderApproval={async () => {
                setApprovalBusy(true)
                try {
                  await sendForStakeholderApproval()
                } finally {
                  setApprovalBusy(false)
                }
              }}
              onStakeholderApprove={async (role) => {
                setApprovalBusy(true)
                try {
                  await stakeholderApprove(role)
                } finally {
                  setApprovalBusy(false)
                }
              }}
              onStakeholderRequestReview={async (role, comment) => {
                setApprovalBusy(true)
                try {
                  await stakeholderRequestReview(role, comment)
                } finally {
                  setApprovalBusy(false)
                }
              }}
              onCmResend={async (reply) => {
                setApprovalBusy(true)
                try {
                  await cmResendForApproval(reply)
                } finally {
                  setApprovalBusy(false)
                }
              }}
            />

            {isAdmin ? (
              <IepPendingChangesPanel items={pendingChanges} onApprove={approveChanges} onReturn={returnChanges} />
            ) : null}

            <IepBuilderSections
              sections={sections}
              goals={goals}
              caseId={caseId}
              childName={childName}
              readOnly={readOnly}
              suggestedGoals={suggestedGoals}
              onPatchSection={patchSection}
              onEditGoal={setEditGoal}
              onRemoveGoal={(g) => deleteGoal(g.iep_goal_id)}
              onLinkStrategy={(g) => {
                setStrategyGoal(g)
                setGoalModal(true)
              }}
              onMarkAchieved={(g) => markAchieved(g.iep_goal_id)}
              onPatchGoal={patchGoal}
              onAddGoal={() => {
                setStrategyGoal(null)
                setGoalModal(true)
              }}
              onImportSuggestedGoal={handleImportSuggestedGoal}
              aggregatedInputs={aggregatedInputs}
            />

            <IepReviewSuggestionsPanel caseId={caseId} iepPlanId={workspace?.iep_plan_id} />
          </ClinicalBuilderShell>
        </div>
      </div>

      {goalModal ? (
        <StudentGoalCreateModal
          caseId={caseId}
          clinicalReportId={workspace?.report_id}
          reportType="iep"
          childName={childName || caseCode || 'Student'}
          preSelectedGoal={strategyGoal}
          initialRepositoryKind={strategyGoal ? 'strategies' : 'goals'}
          onClose={() => {
            setGoalModal(false)
            setStrategyGoal(null)
          }}
          onCreated={async () => {
            setGoalModal(false)
            setStrategyGoal(null)
            await loadWorkspace()
          }}
        />
      ) : null}

      <IepGoalEditor
        open={Boolean(editGoal)}
        goal={editGoal}
        onClose={() => setEditGoal(null)}
        onSave={async (draft) => {
          await patchGoal(draft.iep_goal_id, draft)
          setEditGoal(null)
        }}
      />
    </div>
  )
}
