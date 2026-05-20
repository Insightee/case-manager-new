export function formatSessionTimeRange(session) {
  if (!session?.actual_start_at || !session?.actual_end_at) return null
  const start = new Date(session.actual_start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const end = new Date(session.actual_end_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return `${start} – ${end}`
}

export function isLogEditable(log) {
  if (!log || log.approval_status !== 'PENDING') return false
  if (log.can_edit === true) return true
  if (log.can_edit === false) return false
  if (!log.submitted_at) return false
  const until = log.editable_until
    ? new Date(log.editable_until).getTime()
    : new Date(log.submitted_at).getTime() + 24 * 60 * 60 * 1000
  return Date.now() < until
}

export function logToFormState(log) {
  return {
    attendance_status: log.attendance_status || 'PRESENT',
    session_notes: log.session_notes || '',
    activities_done: log.activities_done || '',
    goals_addressed: log.goals_addressed || '',
    observations: log.observations || '',
    follow_ups: log.follow_ups || '',
    parent_notes: log.parent_notes || '',
    late_reason: log.late_reason || '',
  }
}

export function validateSessionLogForm(form, { isLateSession }) {
  if (!form.activities_done?.trim() || form.activities_done.trim().length < 3) {
    return 'Describe what you did in this session (at least a few words).'
  }
  if (isLateSession && !form.late_reason?.trim()) {
    return 'Add a late reason for past-day sessions.'
  }
  return ''
}
