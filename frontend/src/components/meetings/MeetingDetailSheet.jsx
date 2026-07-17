import { Link } from 'react-router-dom'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import { mapCmMeetingToCalendarEvent } from '../../lib/googleCalendar.js'
import { AddToGoogleCalendarButton } from '../shared/AddToGoogleCalendarButton.jsx'
import { STATUS_LABELS } from './meetingConstants.js'
import { formatAttendeeList, meetingTypeLabel } from './meetingUtils.js'

function StatusBadge({ status }) {
  const s = STATUS_LABELS[status] || { label: status, bg: '#f1f5f9', color: '#475569' }
  return (
    <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '3px 8px', borderRadius: 6, background: s.bg, color: s.color }}>
      {s.label}
    </span>
  )
}

export function MeetingDetailSheet({
  open,
  meeting,
  onClose,
  readOnly = false,
  caseLinkPrefix = '/admin/cases',
  onReschedule,
  onCancel,
  onAddNotes,
}) {
  if (!open || !meeting) return null

  const typeLabel = meetingTypeLabel(meeting)
  const attendeeLine = formatAttendeeList(meeting)
  const hasNotes = meeting.notes_concerns || meeting.notes_follow_up || meeting.notes_action || meeting.notes_other
  const calendarEvent = meeting.status === 'SCHEDULED' ? mapCmMeetingToCalendarEvent(meeting) : null
  const canManage = !readOnly && meeting.status === 'SCHEDULED'

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 sm:items-center sm:p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{meeting.title || typeLabel}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {formatDisplayDateTime(meeting.scheduled_date, meeting.scheduled_time)}
              {meeting.duration_minutes ? ` · ${meeting.duration_minutes} min` : ''}
            </p>
          </div>
          <StatusBadge status={meeting.status} />
        </div>

        <div className="space-y-3 text-sm text-slate-600">
          {meeting.case_id ? (
            <p>
              Case:{' '}
              <Link className="font-semibold text-indigo-700" to={`${caseLinkPrefix}/${meeting.case_id}?tab=overview`}>
                {meeting.case_code || `#${meeting.case_id}`}
              </Link>
              {meeting.child_name ? ` · ${meeting.child_name}` : ''}
            </p>
          ) : meeting.child_name ? (
            <p>Child: <strong>{meeting.child_name}</strong></p>
          ) : null}
          {attendeeLine ? <p>Attendees: {attendeeLine}</p> : null}
          {meeting.meeting_url ? (
            <p>
              <a href={meeting.meeting_url} target="_blank" rel="noreferrer" className="font-semibold text-indigo-700">
                Join meeting
              </a>
            </p>
          ) : null}
          {meeting.guest_emails?.length > 0 ? <p>Guests: {meeting.guest_emails.join(', ')}</p> : null}
        </div>

        {hasNotes ? (
          <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
            {meeting.notes_concerns ? <p className="mb-1"><strong>Concerns:</strong> {meeting.notes_concerns}</p> : null}
            {meeting.notes_follow_up ? <p className="mb-1"><strong>Follow-up:</strong> {meeting.notes_follow_up}</p> : null}
            {meeting.notes_action ? <p className="mb-1"><strong>Actions:</strong> {meeting.notes_action}</p> : null}
            {meeting.notes_other ? <p><strong>Other:</strong> {meeting.notes_other}</p> : null}
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-2">
          {calendarEvent ? <AddToGoogleCalendarButton event={calendarEvent} variant="inline" /> : null}
          {!readOnly && meeting.status !== 'CANCELLED' ? (
            <button
              type="button"
              className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-semibold text-indigo-800"
              onClick={() => onAddNotes?.(meeting)}
            >
              {hasNotes ? 'Edit notes' : 'Add notes / complete'}
            </button>
          ) : null}
          {canManage ? (
            <>
              <button
                type="button"
                className="rounded-lg border border-indigo-200 bg-white px-3 py-2 text-sm font-semibold text-indigo-700"
                onClick={() => onReschedule?.(meeting)}
              >
                Reschedule
              </button>
              <button
                type="button"
                className="rounded-lg border border-red-200 bg-white px-3 py-2 text-sm font-semibold text-red-700"
                onClick={() => onCancel?.(meeting)}
              >
                Cancel meeting
              </button>
            </>
          ) : null}
          <button
            type="button"
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
