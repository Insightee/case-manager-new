/** Shared session-log list helpers (therapist + client portals). */

export function isChildAbsentLog(log) {
  const att = log?.attendance_status
  return att === 'CLIENT_ABSENT' || att === 'CLIENT_LEAVE'
}

export function isLeaveLog(log) {
  return log?.attendance_status === 'THERAPIST_LEAVE'
}

export function isAbsenceAttendanceLog(log) {
  return isChildAbsentLog(log) || isLeaveLog(log)
}

export function isVirtualAbsenceLog(log) {
  return Number(log?.id) < 0 || isAbsenceAttendanceLog(log)
}

export function logSessionDateMs(log) {
  if (!log?.scheduled_date) return 0
  return new Date(`${log.scheduled_date}T12:00:00`).getTime()
}

/** Newest session dates first; stable tie-break on session id. */
export function sortLogsBySessionDate(list) {
  return [...list].sort((a, b) => {
    const byDate = logSessionDateMs(b) - logSessionDateMs(a)
    if (byDate !== 0) return byDate
    return (Number(b.session_id) || Number(b.id) || 0) - (Number(a.session_id) || Number(a.id) || 0)
  })
}

/** Session ids with a filed absence/leave (pending or approved virtual log). */
export function absenceCoveredSessionIds(logs) {
  const ids = new Set()
  for (const log of logs || []) {
    if (isAbsenceAttendanceLog(log) && log.session_id != null) {
      ids.add(Number(log.session_id))
    }
  }
  return ids
}

export function filterSessionsWithoutAbsence(sessions, logs) {
  const blocked = absenceCoveredSessionIds(logs)
  if (!blocked.size) return sessions || []
  return (sessions || []).filter((s) => !blocked.has(Number(s.id)))
}
