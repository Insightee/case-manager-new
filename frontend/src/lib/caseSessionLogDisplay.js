import { formatLogCommentCount } from './sessionLogComments.js'
import { formatDisplayDateLabel } from './datetime.js'
import { formatClockRange, formatEditedRange } from './sessionTimes.js'

/** Merged session/log record for date and clock display. */
export function resolveSessionLogTimesSource(session, log) {
  return session || log || null
}

/** Primary card title: friendly date · clock → corrected when applicable. */
export function formatCaseSessionLogCardTitle(session, log) {
  const source = resolveSessionLogTimesSource(session, log)
  if (!source?.scheduled_date) return 'Session date unavailable'

  const datePart = formatDisplayDateLabel(source.scheduled_date)
  const clockRange = formatClockRange(source)
  const editedRange =
    source.actual_times_edited || source.edited_start_at ? formatEditedRange(source) : null

  let title = datePart
  if (clockRange) title += ` · ${clockRange}`
  if (editedRange) title += ` → ${editedRange}`
  return title
}

/** Secondary line: session, therapist, log id, comment count. */
export function formatCaseSessionLogCardMeta(session, log) {
  const parts = []
  const sessionId = session?.id ?? log?.session_id

  if (sessionId != null) parts.push(`Session #${sessionId}`)

  const therapistLabel = session?.therapist_name || log?.therapist_name
  if (therapistLabel) {
    parts.push(therapistLabel)
  } else {
    const therapistId = session?.therapist_user_id ?? log?.therapist_user_id
    if (therapistId) parts.push(`Therapist #${therapistId}`)
  }

  if (log?.id) parts.push(`Log #${log.id}`)

  const commentLabel = formatLogCommentCount(log?.comment_count)
  if (commentLabel) parts.push(commentLabel)

  return parts.join(' · ')
}

export function caseSessionLogCardTone(session, log) {
  if (log?.approval_status === 'PENDING') {
    return log?.resubmitted_at ? 'resubmitted' : 'pending'
  }
  if (log?.approval_status === 'REJECTED') return 'rejected'
  return 'default'
}
