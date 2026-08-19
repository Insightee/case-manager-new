import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clinicalReportSectionPath } from '../../../lib/clinicalReportPaths.js'
import { StudentGoalCreateModal } from '../../clinical/goals-strategy/StudentGoalCreateModal.jsx'
import { StitchWorkspaceSubhead } from '../observation/stitch/ObservationStitchBlocks.jsx'
import { useIepReport } from '../hooks/useIepReport.js'
import { ClinicalBuilderShell } from '../shared/ClinicalBuilderShell.jsx'
import { ClinicalReportEmptyState, ClinicalReportNotice } from '../shared/ClinicalReportNotice.jsx'
import { IepApprovalPanel } from './IepApprovalPanel.jsx'
import { IepGoalEditor } from './IepGoalCard.jsx'
import { IepBuilderSections } from './IepBuilderSections.jsx'
import { IepPendingChangesPanel } from './IepPendingChangesPanel.jsx'

function sectionData(sections, key) {
  return sections?.find((s) => s.key === key) || {}
}

export function IepBuilderPage({ caseId, caseCode, childName, variant = 'therapist' }) {
  const navigate = useNavigate()
  const sectionPath = (view) => clinicalReportSectionPath({ caseId, section: 'iep', view, variant })
  const isAdmin = variant === 'admin'

  const {
    workspace,
    availableGoals,
    summary,
    pendingChanges,
    loading,
    error,
    saving,
    loadWorkspace,
    generateFromObservation,
    patchSection,
    addGoal,
    patchGoal,
    deleteGoal,
    markAchieved,
    submitReport,
    saveDraft,
    approveChanges,
    returnChanges,
    sendForStakeholderApproval,
    stakeholderApprove,
    stakeholderRequestReview,
    cmResendForApproval,
    AUTO_SAVE_MS,
  } = useIepReport(caseId)

  const [goalModal, setGoalModal] = useState(false)
  const [strategyGoal, setStrategyGoal] = useState(null)
  const [editGoal, setEditGoal] = useState(null)
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

  const statusLabel = (workspace?.status || 'draft').replace(/_/g, ' ').toUpperCase()

  const goPreview = useCallback(() => {
    navigate(sectionPath('preview'))
  }, [navigate, caseId, variant])

  if (loading && !workspace) {
    return <p className="text-sm text-slate-600 m-0">Loading IEP builder…</p>
  }

  if (!workspace?.report_id) {
    return (
      <ClinicalReportEmptyState
        title="IEP builder could not load"
        message={
          error ||
          'No IEP workspace is available for this client yet. The clinical reports API may not be enabled on this server.'
        }
        backHref={`/therapist/reports?case_id=${caseId}`}
        onRetry={() => loadWorkspace()}
      />
    )
  }

  return (
    <div className="iep-workspace clinical-report-ui forest-light pb-24">
      <StitchWorkspaceSubhead
        caseCode={caseCode}
        saving={saving}
        title="IEP Report Builder"
      />

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
        {error ? <ClinicalReportNotice className="mb-4">{error}</ClinicalReportNotice> : null}

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
          onAddGoal={() => {
            setStrategyGoal(null)
            setGoalModal(true)
          }}
          onImportSuggestedGoal={handleImportSuggestedGoal}
        />
      </ClinicalBuilderShell>

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
