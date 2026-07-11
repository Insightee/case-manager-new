import { formatSessionActualRange, todayIsoIST } from './datetime.js'

export { todayIsoIST }

function formatWallClock(t) {
  if (!t) return null
  return String(t).slice(0, 5)
}

/** Prefer actual check-in/out (IST); fall back to scheduled start_time/end_time. */
export function formatSessionDisplayRange(session) {
  const actual = formatSessionActualRange(session, { suffix: '' })
  if (actual) return actual
  const start = formatWallClock(session?.start_time)
  const end = formatWallClock(session?.end_time)
  if (start && end) return `${start}–${end}`
  return start || end || null
}

export function formatSessionTimeRange(session) {
  return formatSessionActualRange(session)
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

export function isLogResubmittable(log) {
  return log?.approval_status === 'REJECTED' || log?.can_resubmit === true
}

export function canEditLog(log) {
  return isLogEditable(log) || isLogResubmittable(log)
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

export function isLateSessionLog(session) {
  if (!session?.scheduled_date) return false
  return session.scheduled_date < todayIsoIST()
}
