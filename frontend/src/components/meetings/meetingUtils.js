import { ATTENDEE_ROLE_LABELS, MEETING_TYPES } from './meetingConstants.js'

export function formatAttendeeList(meeting) {
  if (meeting.attendees?.length) {
    return meeting.attendees.map((a) => {
      const role = ATTENDEE_ROLE_LABELS[a.role] || a.role
      return `${role}: ${a.name}`
    }).join(' · ')
  }
  const parts = []
  if (meeting.parent_name) parts.push(`Client: ${meeting.parent_name}`)
  if (meeting.therapist_name) parts.push(`Therapist: ${meeting.therapist_name}`)
  if (meeting.case_manager_name) parts.push(`CM: ${meeting.case_manager_name}`)
  return parts.join(' · ')
}

export function meetingTypeLabel(meeting) {
  return (
    MEETING_TYPES.find((t) => t.value === meeting.meeting_type)?.label
    || (meeting.meeting_type === 'SUPERVISION' ? 'Internal meeting' : meeting.meeting_type)
  )
}

/** Primary label for cards, calendar, and detail headers. */
export function meetingDisplayTitle(meeting) {
  const title = (meeting.title || '').trim()
  if (title) return title
  const otherReason = (meeting.other_reason || '').trim()
  if (meeting.meeting_type === 'OTHER' && otherReason) return otherReason
  return meetingTypeLabel(meeting)
}

export function parseMeetingIdFromGridEvent(event) {
  if (!event) return null
  if (event.meeting_id) return Number(event.meeting_id)
  if (typeof event.id === 'string' && event.id.startsWith('cm-meeting-')) {
    return Number(event.id.replace('cm-meeting-', ''))
  }
  return null
}

export function padHour(hour) {
  return `${String(hour).padStart(2, '0')}:00`
}

export function buildMeetingsAvailabilityQuery({
  targetDate,
  durationMinutes,
  caseManagerId,
  therapistId,
  adminIds = [],
}) {
  const params = new URLSearchParams()
  params.set('target_date', targetDate)
  params.set('duration_minutes', String(durationMinutes || 30))
  if (caseManagerId) params.set('case_manager_id', String(caseManagerId))
  if (therapistId) params.set('therapist_id', String(therapistId))
  for (const id of adminIds) {
    if (id) params.append('admin_ids', String(id))
  }
  return params.toString()
}
