import { StudentGoalCreateModal } from '../goals-strategy/StudentGoalCreateModal.jsx'

/** Session log — add strategy linked to an active goal card. */
export function AddStrategyOverlay({ caseId, logId, goalCardId, goalLabel, childName, onClose, onCreated }) {
  return (
    <StudentGoalCreateModal
      caseId={caseId}
      reportType="session"
      logId={logId}
      childName={goalLabel || childName || 'Student'}
      preSelectedGoal={{ goal_card_id: goalCardId, label: goalLabel }}
      initialRepositoryKind="strategies"
      onClose={onClose}
      onCreated={onCreated}
    />
  )
}
