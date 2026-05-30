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

/** DD-MM-YY in IST (e.g. 30-05-26). */
export function formatDateIN(iso) {
  const d = parseApiDatetime(iso)
  if (!d) return null
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: APP_TIMEZONE,
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
  }).formatToParts(d)
  const day = parts.find((p) => p.type === 'day')?.value
  const month = parts.find((p) => p.type === 'month')?.value
  const year = parts.find((p) => p.type === 'year')?.value
  return day && month && year ? `${day}-${month}-${year}` : null
}

/** 12-hour clock with IST suffix (e.g. 9:30 AM IST). */
export function formatTimeIN12(iso, { suffix = ' IST' } = {}) {
  const d = parseApiDatetime(iso)
  if (!d) return null
  const time = d.toLocaleTimeString('en-IN', {
    timeZone: APP_TIMEZONE,
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
  return `${time}${suffix}`
}

/** Combined Indian display: DD-MM-YY, 9:30 AM IST */
export function formatDateTimeIN(iso) {
  const datePart = formatDateIN(iso)
  const timePart = formatTimeIN12(iso, { suffix: '' })
  if (!datePart || !timePart) return null
  return `${datePart}, ${timePart} IST`
}

export function formatTimeIST(iso, options = {}) {
  const use12h = options.hour12 !== false
  if (use12h && !options.hour && !options.minute) {
    return formatTimeIN12(iso, { suffix: options.suffix ?? ' IST' })
  }
  const d = parseApiDatetime(iso)
  if (!d) return null
  return d.toLocaleTimeString('en-IN', {
    timeZone: APP_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: use12h,
    ...options,
  })
}

export function formatSessionActualRange(session, { suffix = ' IST' } = {}) {
  if (!session?.actual_start_at) return null
  const start = formatTimeIN12(session.actual_start_at, { suffix: '' })
  if (!session.actual_end_at) {
    return start ? `Started ${start}${suffix}` : null
  }
  const end = formatTimeIN12(session.actual_end_at, { suffix: '' })
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

/** Format YYYY-MM-DD API date as DD-MM-YY without timezone shift. */
export function formatApiDateIN(dateStr) {
  if (!dateStr) return null
  const [y, m, d] = String(dateStr).slice(0, 10).split('-')
  if (!y || !m || !d) return null
  return `${d}-${m}-${y.slice(-2)}`
}
