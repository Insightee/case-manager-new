/** India operations timezone — display and business-date comparisons for therapists. */
export const APP_TIMEZONE = 'Asia/Kolkata'

const ISO_HAS_TZ = /[zZ]|[+-]\d{2}:?\d{2}$/

/** Parse API ISO strings; naive values are treated as UTC. */
export function parseApiDatetime(iso) {
  if (!iso) return null
  const s = String(iso).trim()
  const normalized = ISO_HAS_TZ.test(s) ? s : `${s}Z`
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatTimeIST(iso, options = {}) {
  const d = parseApiDatetime(iso)
  if (!d) return null
  return d.toLocaleTimeString('en-IN', {
    timeZone: APP_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...options,
  })
}

export function formatSessionActualRange(session, { suffix = ' IST' } = {}) {
  if (!session?.actual_start_at) return null
  const start = formatTimeIST(session.actual_start_at)
  if (!session.actual_end_at) {
    return start ? `Started ${start}${suffix}` : null
  }
  const end = formatTimeIST(session.actual_end_at)
  return start && end ? `${start} – ${end}${suffix}` : null
}

/** Today's calendar date in IST (YYYY-MM-DD). */
export function todayIsoIST() {
  return new Date().toLocaleDateString('en-CA', { timeZone: APP_TIMEZONE })
}

export function actualDurationMinsIST(startIso, endIso) {
  const start = parseApiDatetime(startIso)
  const end = parseApiDatetime(endIso)
  if (!start || !end) return null
  const diff = Math.round((end.getTime() - start.getTime()) / 60000)
  return diff > 0 ? diff : null
}

/** True when actual clock-in is more than thresholdMins after scheduled start (IST wall clock). */
export function isStartedLateOnSchedule(actualStartIso, scheduledDate, scheduledStartTime, thresholdMins = 5) {
  const actual = parseApiDatetime(actualStartIso)
  if (!actual || !scheduledDate || !scheduledStartTime) return false
  const [h, m] = String(scheduledStartTime).slice(0, 5).split(':').map(Number)
  const sched = new Date(`${scheduledDate}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00+05:30`)
  if (Number.isNaN(sched.getTime())) return false
  return (actual.getTime() - sched.getTime()) / 60000 > thresholdMins
}
