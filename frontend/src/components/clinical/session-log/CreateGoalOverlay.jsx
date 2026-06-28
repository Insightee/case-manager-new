import { StudentGoalCreateModal } from '../goals-strategy/StudentGoalCreateModal.jsx'

/** Session log overlay — canonical goal create modal. */
export function CreateGoalOverlay({
  caseId,
  sessionId,
  logId,
  reportType = 'session',
  childName,
  onClose,
  onCreated,
}) {
  return (
    <StudentGoalCreateModal
      caseId={caseId}
      reportType={reportType}
      logId={logId}
      sessionId={sessionId}
      childName={childName || 'Student'}
      onClose={onClose}
      onCreated={onCreated}
    />
  )
}
