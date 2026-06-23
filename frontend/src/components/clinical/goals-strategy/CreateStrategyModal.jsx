import { StudentGoalCreateModal } from './StudentGoalCreateModal.jsx'

/** @deprecated Use StudentGoalCreateModal with preSelectedGoal — kept for import stability. */
export function CreateStrategyModal({
  caseId,
  logId,
  goalCardId,
  goalLabel = '',
  clinicalReportId,
  iepGoalId,
  onClose,
  onCreated,
}) {
  return (
    <StudentGoalCreateModal
      caseId={caseId}
      clinicalReportId={clinicalReportId}
      reportType={clinicalReportId ? 'iep' : 'session'}
      logId={logId}
      childName={goalLabel || 'Student'}
      preSelectedGoal={{
        goal_card_id: goalCardId,
        iep_goal_id: iepGoalId,
        label: goalLabel,
      }}
      initialRepositoryKind="strategies"
      standaloneStrategy={!goalCardId && !iepGoalId}
      onClose={onClose}
      onCreated={onCreated}
    />
  )
}
