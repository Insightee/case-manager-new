import { todayIsoIST } from './datetime.js'

const ONGOING_SESSION_STATUSES = new Set(['SCHEDULED', 'IN_PROGRESS'])
const CHILD_LEAVE_ATTENDANCE = new Set(['CLIENT_ABSENT', 'CLIENT_LEAVE'])

export const CASE_SESSION_LOG_VIEW_MODES = [
  { value: 'month', label: 'Month' },
  { value: 'day', label: 'Day' },
  { value: 'all', label: 'All' },
]

export const CASE_SESSION_LOG_STATUS_FILTERS = [
  { value: '', label: 'All statuses' },
  { value: 'approved', label: 'Approved' },
  { value: 'pending_review', label: 'Pending review' },
  { value: 'ongoing', label: 'Ongoing' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'no_log', label: 'No log submitted' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'child_on_leave', label: 'Child on leave' },
  { value: 'therapist_on_leave', label: 'Therapist on leave' },
  { value: 'resubmitted', label: 'Resubmitted' },
  { value: 'times_edited', label: 'Times edited' },
]

export function sessionDateIso(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

export function currentMonthIso() {
  return todayIsoIST().slice(0, 7)
}

export function defaultCaseSessionLogFilters() {
  const today = todayIsoIST()
  return {
    viewMode: 'month',
    selectedMonth: today.slice(0, 7),
    selectedDate: today,
    statusFilter: 'approved',
  }
}

export function formatCaseSessionLogMonthLabel(monthValue) {
  const [year, month] = monthValue.split('-').map(Number)
  if (!year || !month) return monthValue
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

export function caseSessionLogStatusLabel(statusFilter) {
  return CASE_SESSION_LOG_STATUS_FILTERS.find((f) => f.value === statusFilter)?.label || 'All statuses'
}

function isChildOnLeave(session, log) {
  const sessionStatus = String(session?.status || '').toUpperCase()
  const attendance = log?.attendance_status
  return sessionStatus === 'CLIENT_ABSENT' || CHILD_LEAVE_ATTENDANCE.has(attendance)
}

function isTherapistOnLeave(session, log) {
  const sessionStatus = String(session?.status || '').toUpperCase()
  return sessionStatus === 'THERAPIST_LEAVE' || log?.attendance_status === 'THERAPIST_LEAVE'
}

export function matchesCaseSessionLogView(scheduledDate, viewMode, selectedDate, selectedMonth) {
  const iso = sessionDateIso(scheduledDate)
  if (viewMode === 'all') return true
  if (!iso) return false
  if (viewMode === 'month') return iso.startsWith(selectedMonth)
  return iso === selectedDate
}

export function matchesCaseSessionLogStatus(session, log, statusFilter, hasTimeEdit = false) {
  if (!statusFilter) return true

  const sessionStatus = String(session?.status || '').toUpperCase()
  const approvalStatus = String(log?.approval_status || '').toUpperCase()
  const hasLog = Boolean(log)
  const isOngoing = ONGOING_SESSION_STATUSES.has(sessionStatus) && !hasLog

  switch (statusFilter) {
    case 'approved':
      return approvalStatus === 'APPROVED'
    case 'pending_review':
      return approvalStatus === 'PENDING'
    case 'rejected':
      return approvalStatus === 'REJECTED'
    case 'ongoing':
      return isOngoing
    case 'no_log':
      return !hasLog && !ONGOING_SESSION_STATUSES.has(sessionStatus)
    case 'cancelled':
      return sessionStatus === 'CANCELLED'
    case 'child_on_leave':
      return isChildOnLeave(session, log)
    case 'therapist_on_leave':
      return isTherapistOnLeave(session, log)
    case 'resubmitted':
      return Boolean(log?.resubmitted_at)
    case 'times_edited':
      return hasTimeEdit
    default:
      return true
  }
}

export function filterCaseSessionRows({
  sessions,
  logsBySessionId,
  orphanLogs,
  viewMode,
  selectedDate,
  selectedMonth,
  statusFilter,
  highlightSessionId,
  sessionHasTimeEdit,
}) {
  const filteredSessions = sessions.filter((session) => {
    if (highlightSessionId && String(session.id) === String(highlightSessionId)) return true
    const log = logsBySessionId.get(session.id)
    if (!matchesCaseSessionLogView(session.scheduled_date, viewMode, selectedDate, selectedMonth)) {
      return false
    }
    return matchesCaseSessionLogStatus(
      session,
      log,
      statusFilter,
      sessionHasTimeEdit(session, log),
    )
  })

  const filteredOrphanLogs = orphanLogs.filter((log) => {
    if (!matchesCaseSessionLogView(log.scheduled_date, viewMode, selectedDate, selectedMonth)) {
      return false
    }
    return matchesCaseSessionLogStatus(null, log, statusFilter, sessionHasTimeEdit(null, log))
  })

  return { filteredSessions, filteredOrphanLogs }
}

export function caseSessionLogEmptyMessage({ viewMode, selectedDate, selectedMonth, statusFilter }) {
  const statusLabel = caseSessionLogStatusLabel(statusFilter)
  if (viewMode === 'day') {
    return `No session logs for ${selectedDate}${statusFilter ? ` with status ${statusLabel}` : ''}.`
  }
  if (viewMode === 'month') {
    return `No session logs for ${formatCaseSessionLogMonthLabel(selectedMonth)}${statusFilter ? ` with status ${statusLabel}` : ''}.`
  }
  return statusFilter
    ? `No session logs with status ${statusLabel}.`
    : 'No session logs match the current filters.'
}
