import { WeeklyScheduleDrawer } from '../therapist/WeeklyScheduleDrawer.jsx'

/** @deprecated Use WeeklyScheduleDrawer — kept for admin/case imports. */
export function QuickRecurringModal({
  open,
  onClose,
  onSuccess,
  fixedCaseId,
  therapistUserId,
  weekStart,
  weekEnd,
}) {
  const today = new Date().toISOString().slice(0, 10)
  return (
    <WeeklyScheduleDrawer
      open={open}
      onClose={onClose}
      onApplied={onSuccess}
      weekStart={weekStart || today}
      weekEnd={weekEnd || today}
      therapistId={therapistUserId}
      therapistUserIdProp={therapistUserId}
      fixedCaseId={fixedCaseId}
      initialTab="recurring"
      singleTab="recurring"
    />
  )
}
