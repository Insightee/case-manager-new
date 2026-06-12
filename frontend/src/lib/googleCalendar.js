import { APP_TIMEZONE, formatApiDateIN, formatDisplayDateTimeRange } from './datetime.js'

const DATE_FMT = /^\d{4}-\d{2}-\d{2}$/
const TIME_FMT = /^(\d{1,2}):(\d{2})(?::(\d{2}))?$/
const GCAL_TEMPLATE_BASE = 'https://calendar.google.com/calendar/render'
const GOOGLE_ACCOUNT_CHOOSER = 'https://accounts.google.com/AccountChooser'

function pad2(n) {
  return String(n).padStart(2, '0')
}

/** Build an absolute app URL for calendar event details (works on localhost). */
export function buildAppDeepLink(path = '/') {
  const normalized = path.startsWith('/') ? path : `/${path}`
  if (typeof window !== 'undefined' && window.location?.origin) {
    return `${window.location.origin}${normalized}`
  }
  return normalized
}

function parseWallClockTime(timeStr) {
  if (!timeStr) return { hours: 9, minutes: 0, seconds: 0 }
  const match = String(timeStr).trim().match(TIME_FMT)
  if (!match) return { hours: 9, minutes: 0, seconds: 0 }
  return {
    hours: Number(match[1]),
    minutes: Number(match[2]),
    seconds: Number(match[3] || 0),
  }
}

export function durationMinutesFromTimes(startTime, endTime) {
  if (!startTime || !endTime) return null
  const start = parseWallClockTime(startTime)
  const end = parseWallClockTime(endTime)
  const startMins = start.hours * 60 + start.minutes
  const endMins = end.hours * 60 + end.minutes
  const diff = endMins - startMins
  return diff > 0 ? diff : null
}

function addMinutesToWallClock(dateStr, timeStr, minutes) {
  const { hours, minutes: mins, seconds } = parseWallClockTime(timeStr)
  const total = hours * 60 + mins + Math.max(minutes, 15)
  const endHours = Math.floor(total / 60) % 24
  const endMins = total % 60
  const datePart = String(dateStr).slice(0, 10)
  const start = `${datePart.replace(/-/g, '')}T${pad2(hours)}${pad2(mins)}${pad2(seconds)}`
  const end = `${datePart.replace(/-/g, '')}T${pad2(endHours)}${pad2(endMins)}00`
  return `${start}/${end}`
}

/**
 * Build a Google Calendar "Add event" template URL.
 * Uses ctz + local wall-clock dates (Asia/Kolkata by default) — matches backend helper.
 */
export function buildGoogleCalendarUrl({
  title,
  scheduledDate,
  startTime,
  endTime,
  durationMinutes,
  details = '',
  location = '',
  timezone = APP_TIMEZONE,
} = {}) {
  if (!scheduledDate || !DATE_FMT.test(String(scheduledDate).slice(0, 10))) return null
  const dateStr = String(scheduledDate).slice(0, 10)
  const start = startTime || '09:00'
  let duration = Number(durationMinutes)
  if (!Number.isFinite(duration) || duration <= 0) {
    duration = durationMinutesFromTimes(start, endTime) || 30
  }
  duration = Math.max(Math.round(duration), 15)

  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: (title || 'Appointment').slice(0, 1024),
    dates: addMinutesToWallClock(dateStr, start, duration),
    ctz: timezone || APP_TIMEZONE,
  })
  if (details?.trim()) params.set('details', details.trim().slice(0, 5000))
  if (location?.trim()) params.set('location', location.trim().slice(0, 1024))
  return `${GCAL_TEMPLATE_BASE}?${params.toString()}`
}

/** Public template URL only — never workspace or /a/domain paths. */
export function buildGoogleCalendarAccountChooserUrl(eventOrUrl) {
  const calendarUrl =
    typeof eventOrUrl === 'string' ? eventOrUrl : buildGoogleCalendarUrl(eventOrUrl)
  if (!calendarUrl || !calendarUrl.startsWith(GCAL_TEMPLATE_BASE)) return null
  return `${GOOGLE_ACCOUNT_CHOOSER}?continue=${encodeURIComponent(calendarUrl)}`
}

export function normalizeSlotForCalendar(slot) {
  if (!slot) return null
  const slot_date = slot.slot_date || slot.date || slot.slotDate
  if (!slot_date) return null
  return {
    ...slot,
    slot_date: String(slot_date).slice(0, 10),
    start_time: slot.start_time || slot.startTime || null,
    end_time: slot.end_time || slot.endTime || null,
    child_name: slot.child_name || slot.childName || null,
    case_code: slot.case_code || slot.caseCode || null,
    therapist_name: slot.therapist_name || slot.therapistName || null,
  }
}

export function formatCalendarEventWhen(event) {
  if (!event?.scheduledDate) return null
  return (
    formatDisplayDateTimeRange(event.scheduledDate, event.startTime, event.endTime)
    || formatApiDateIN(event.scheduledDate)
  )
}

function joinDetails(lines) {
  return lines.filter(Boolean).join('\n')
}

export function mapSlotToCalendarEvent(slot, { deepLinkPath = '/parent/book' } = {}) {
  const normalized = normalizeSlotForCalendar(slot)
  if (!normalized?.slot_date) return null
  const child = normalized.child_name || normalized.case_code
  const title = child ? `Therapy session · ${child}` : 'Therapy session'
  const details = joinDetails([
    normalized.case_code ? `Case: ${normalized.case_code}` : null,
    normalized.id ? `Booking ID: ${normalized.id}` : null,
    normalized.therapist_name ? `Therapist: ${normalized.therapist_name}` : null,
    buildAppDeepLink(deepLinkPath),
  ])
  return {
    title,
    scheduledDate: normalized.slot_date,
    startTime: normalized.start_time,
    endTime: normalized.end_time,
    details,
    location: normalized.location || '',
  }
}

const CM_TYPE_LABELS = {
  CLIENT_ONLY: 'Progress review',
  CLIENT_AND_THERAPIST: 'Care coordination',
  IEP_MEETING: 'IEP discussion',
}

export function mapCmMeetingToCalendarEvent(meeting, { deepLinkPath = '/admin/cm-meetings' } = {}) {
  if (!meeting?.scheduled_date) return null
  const typeLabel =
    CM_TYPE_LABELS[meeting.meeting_type]
    || (meeting.meeting_type === 'SUPERVISION' ? 'Internal meeting' : meeting.meeting_type)
  const child = meeting.child_name
  const title = meeting.title || (child ? `${typeLabel} · ${child}` : typeLabel)
  const details = joinDetails([
    meeting.case_code ? `Case: ${meeting.case_code}` : meeting.case_id ? `Case ID: ${meeting.case_id}` : null,
    meeting.id ? `Meeting ID: ${meeting.id}` : null,
    meeting.case_manager_name ? `Case manager: ${meeting.case_manager_name}` : null,
    meeting.meeting_url ? `Join: ${meeting.meeting_url}` : null,
    buildAppDeepLink(deepLinkPath),
  ])
  return {
    title,
    scheduledDate: meeting.scheduled_date,
    startTime: meeting.scheduled_time,
    durationMinutes: meeting.duration_minutes,
    details,
    location: meeting.meeting_url || '',
  }
}

export function mapParentApptToCalendarEvent(appt) {
  if (!appt?.slotDate) return null
  if (appt.isCmMeeting) {
    return mapCmMeetingToCalendarEvent(
      {
        id: appt.rawId,
        scheduled_date: appt.slotDate,
        scheduled_time: appt.startTime,
        duration_minutes: appt.durationMinutes || 30,
        title: appt.title,
        child_name: appt.childName,
        case_manager_name: appt.caseMgrName,
        meeting_type: 'CLIENT_ONLY',
      },
      { deepLinkPath: '/parent/book' },
    )
  }
  const child = appt.childName
  const title = child ? `Therapy session · ${child}` : 'Therapy session'
  const details = joinDetails([
    appt.rawId ? `Booking ID: ${appt.rawId}` : null,
    appt.therapistName ? `Therapist: ${appt.therapistName}` : null,
    buildAppDeepLink('/parent/book'),
  ])
  return {
    title,
    scheduledDate: appt.slotDate,
    startTime: appt.startTime,
    endTime: appt.endTime,
    details,
  }
}

export function mapParentBookedSlotToCalendarEvent({ slot, caseRow, therapistName }) {
  if (!slot) return null
  return mapSlotToCalendarEvent(
    {
      id: slot.id,
      slot_date: slot.slot_date || slot.date,
      start_time: slot.start_time,
      end_time: slot.end_time,
      child_name: caseRow?.childName || caseRow?.child_name,
      case_code: caseRow?.caseCode || caseRow?.case_code,
      therapist_name: therapistName,
    },
    { deepLinkPath: '/parent/book' },
  )
}
