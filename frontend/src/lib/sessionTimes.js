import {
  actualDurationMinsIST,
  formatDisplayDate,
  formatDisplayDateTimeRange,
  formatSessionActualRange,
  formatTimeIST,
  parseApiDatetime,
} from './datetime.js'

function formatWallClock(t) {
  if (!t) return null
  return String(t).slice(0, 5)
}

/** True within 24h of session clock-out, or when the linked log was rejected. */
export function canEditSessionTimes(session, log = null) {
  if (log?.approval_status === 'REJECTED') {
    return session?.status === 'COMPLETED'
  }
  const end = parseApiDatetime(session?.actual_end_at)
  if (!end || session?.status !== 'COMPLETED') return false
  return Date.now() <= end.getTime() + 24 * 60 * 60 * 1000
}

/** Booked slot window from scheduled_date + start_time/end_time. */
export function formatScheduledRange(session) {
  if (!session?.scheduled_date) return null
  const start = formatWallClock(session.start_time)
  const end = formatWallClock(session.end_time)
  const formatted =
    formatDisplayDateTimeRange(session.scheduled_date, start, end)
    || formatDisplayDate(session.scheduled_date, null)
  return formatted || session.scheduled_date
}

/** Clock-in/out from actual_* (immutable record). */
export function formatClockRange(session, { suffix = ' IST' } = {}) {
  return formatSessionActualRange(
    {
      actual_start_at: session?.actual_start_at,
      actual_end_at: session?.actual_end_at,
    },
    { suffix },
  )
}

/** Therapist-proposed correction from edited_*. */
export function formatEditedRange(session, { suffix = ' IST' } = {}) {
  if (!session?.edited_start_at) return null
  return formatSessionActualRange(
    {
      actual_start_at: session.edited_start_at,
      actual_end_at: session.edited_end_at,
    },
    { suffix },
  )
}

/** Duration for display: approved edit when log approved, else clock. */
export function effectiveDurationMins(session, log) {
  const approved = log?.approval_status === 'APPROVED'
  if (approved && session?.edited_start_at && session?.edited_end_at) {
    return actualDurationMinsIST(session.edited_start_at, session.edited_end_at)
  }
  return actualDurationMinsIST(session?.actual_start_at, session?.actual_end_at)
}

export function editedApprovalLabel(log) {
  if (!log) return 'Pending approval'
  if (log.approval_status === 'APPROVED') return 'Approved'
  if (log.approval_status === 'REJECTED') return 'Rejected'
  return 'Pending approval'
}

/** Admin/therapist list title: date · clock → corrected when applicable. */
export function formatSessionLogRowTitle(session, { fmtDate } = {}) {
  if (!session) return '—'
  const datePart = fmtDate ? fmtDate(session.scheduled_date) : session.scheduled_date || '—'
  const clockRange = formatClockRange(session)
  const editedRange =
    session.actual_times_edited || session.edited_start_at ? formatEditedRange(session) : null
  let title = datePart
  if (clockRange) title += ` · ${clockRange}`
  if (editedRange) title += ` → ${editedRange}`
  return title
}

export function sessionHasTimeEdit(session, log) {
  return Boolean(
    session?.actual_times_edited ||
      log?.actual_times_edited ||
      session?.edited_start_at ||
      log?.edited_start_at,
  )
}

export { formatTimeIST }
