/** Normalize session date/time fields from GET /sessions (scheduled_date + start_time). */

const UPCOMING_STATUSES = new Set(['SCHEDULED', 'IN_PROGRESS'])

export function sessionDateKey(session) {
  return session?.scheduled_date || session?.session_date || null
}

export function sessionStartTime(session) {
  return session?.start_time || session?.scheduled_start_time || null
}

export function sessionStartIso(session) {
  const dateKey = sessionDateKey(session)
  if (!dateKey) return null
  const time = sessionStartTime(session) || '00:00'
  const normalized = String(time).length === 5 ? `${time}:00` : String(time)
  const d = new Date(`${dateKey}T${normalized}`)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

export function formatSessionWhen(session) {
  const dateKey = sessionDateKey(session)
  if (!dateKey) return 'Session'
  const time = sessionStartTime(session) || ''
  try {
    const normalized = time ? (String(time).length === 5 ? `${time}:00` : String(time)) : '12:00:00'
    const d = new Date(`${dateKey}T${normalized}`)
    if (Number.isNaN(d.getTime())) return `${dateKey}${time ? ` ${time}` : ''}`
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return `${dateKey}${time ? ` ${time}` : ''}`
  }
}

export function isUpcomingSession(session, now = new Date()) {
  const dateKey = sessionDateKey(session)
  if (!dateKey) return false
  const status = String(session?.status || '').toUpperCase()
  if (!UPCOMING_STATUSES.has(status)) return false
  const today = now.toISOString().slice(0, 10)
  if (dateKey > today) return true
  if (dateKey < today) return false
  const iso = sessionStartIso(session)
  if (!iso) return true
  return new Date(iso) >= now
}

export function sortSessionsByStart(sessions) {
  return [...sessions].sort((a, b) => {
    const da = sessionDateKey(a) || ''
    const db = sessionDateKey(b) || ''
    if (da !== db) return da.localeCompare(db)
    const ta = sessionStartTime(a) || ''
    const tb = sessionStartTime(b) || ''
    return ta.localeCompare(tb)
  })
}

export function filterUpcomingSessions(sessions, now = new Date()) {
  return sortSessionsByStart(sessions.filter((s) => isUpcomingSession(s, now)))
}
