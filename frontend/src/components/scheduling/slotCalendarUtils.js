export const WEEKDAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
export const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export function pad2(n) {
  return String(n).padStart(2, '0')
}

export function dateStr(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

export function startOfWeek(d) {
  const copy = new Date(d)
  const day = copy.getDay()
  copy.setDate(copy.getDate() - day)
  copy.setHours(0, 0, 0, 0)
  return copy
}

export function addDays(d, n) {
  const copy = new Date(d)
  copy.setDate(copy.getDate() + n)
  return copy
}

export function startOfMonth(d) {
  const copy = new Date(d.getFullYear(), d.getMonth(), 1)
  copy.setHours(0, 0, 0, 0)
  return copy
}

export function addMonths(d, n) {
  const copy = new Date(d)
  copy.setMonth(copy.getMonth() + n)
  return copy
}

/** Last calendar day of the month containing `d` */
export function endOfMonth(d) {
  const copy = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  copy.setHours(0, 0, 0, 0)
  return copy
}

export function weekDays(weekStart) {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
}

/** Sunday-start week end date (ISO) containing `dateIso`. */
export function weekEndContaining(dateIso) {
  const start = startOfWeek(new Date(`${dateIso}T12:00:00`))
  return dateStr(addDays(start, 6))
}

/** Hour rows 08–20 for calendar grids */
export function defaultHourRows() {
  return Array.from({ length: 13 }, (_, i) => i + 8)
}

export const THERAPIST_STATUS_STYLES = {
  AVAILABLE: 'bg-emerald-100 text-emerald-900 border-emerald-200',
  BOOKED: 'bg-blue-100 text-blue-900 border-blue-200',
  BOOKED_UNDER_REVIEW: 'bg-amber-50 text-amber-950 border-amber-300',
  BLOCKED: 'bg-slate-200 text-slate-600 border-slate-300',
  HOLIDAY: 'bg-amber-100 text-amber-900 border-amber-200',
  CANCELLED: 'bg-red-50 text-red-800 border-red-200 line-through',
  RESCHEDULED: 'bg-purple-50 text-purple-800 border-purple-200',
  SESSION: 'bg-violet-100 text-violet-900 border-violet-200',
  IN_PROGRESS: 'bg-amber-100 text-amber-900 border-amber-300',
}

export function isCaseUnderReview(caseStatus) {
  return caseStatus === 'PENDING_ALLOTMENT'
}

/** Therapist/parent calendar cell label for a slot or session event. */
export function calendarEventLabel(s, mode = 'therapist') {
  const isParent = mode === 'parent'
  if (isParent) {
    return s.is_mine ? `My session · ${s.start_time}` : `Available · ${s.start_time}`
  }
  if (s.event_type === 'cm_meeting') {
    return `CM · ${s.title || s.child_name || s.case_code || 'Meeting'}`
  }
  if (s.event_type === 'session') {
    const underReview = isCaseUnderReview(s.case_status)
    const who = s.child_name || s.case_code || 'Visit'
    const prefix =
      s.status === 'IN_PROGRESS' ? 'In progress · ' : underReview ? 'Under review · ' : 'Session · '
    return `${prefix}${who}`
  }
  if (s.status === 'BOOKED') {
    const who = s.child_name || s.case_code || 'Booked'
    if (isCaseUnderReview(s.case_status)) {
      return `Under review · ${who}`
    }
    if (s.approval_status === 'PENDING_THERAPIST') {
      return `⏳ ${who}`
    }
    if (s.booking_source === 'PARENT') {
      return `Parent · ${who}`
    }
    return who
  }
  return `${s.start_time}–${s.end_time}`
}

export function calendarEventStyle(s, mode = 'therapist') {
  if (mode === 'parent') {
    return PARENT_SLOT_STYLES[s.is_mine ? 'mine' : 'available']
  }
  if (s.event_type === 'session') {
    return THERAPIST_STATUS_STYLES[s.status === 'IN_PROGRESS' ? 'IN_PROGRESS' : 'SESSION']
  }
  if (s.status === 'BOOKED' && isCaseUnderReview(s.case_status)) {
    return THERAPIST_STATUS_STYLES.BOOKED_UNDER_REVIEW
  }
  return THERAPIST_STATUS_STYLES[s.status] || ''
}

function cmMeetingsAsGridEvents(meetings) {
  return (meetings || []).map((m) => ({
    id: `cm-meeting-${m.id}`,
    event_type: 'cm_meeting',
    status: 'SESSION',
    slot_date: m.date,
    start_time: m.start_time || '09:00',
    end_time: m.end_time,
    child_name: m.child_name,
    case_code: m.case_code,
    title: m.title,
  }))
}

/** Slots, therapy sessions, and CM meetings returned by the calendar API. */
export function calendarGridEvents(calendar) {
  return [
    ...(calendar?.slots || []),
    ...(calendar?.sessions || []),
    ...cmMeetingsAsGridEvents(calendar?.cm_meetings),
  ]
}

export const STATUS_LABELS = {
  AVAILABLE: 'Available',
  BOOKED: 'Booked',
  BLOCKED: 'Blocked',
  HOLIDAY: 'Holiday',
  CANCELLED: 'Cancelled',
  RESCHEDULED: 'Rescheduled',
}

export const PARENT_SLOT_STYLES = {
  available: 'bg-emerald-50 text-emerald-900 border-emerald-300 hover:bg-emerald-100',
  mine: 'bg-indigo-100 text-indigo-900 border-indigo-300 hover:bg-indigo-200',
}
