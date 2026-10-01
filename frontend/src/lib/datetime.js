/** India operations timezone — display and business-date comparisons for therapists. */
export const APP_TIMEZONE = 'Asia/Kolkata'

const ISO_HAS_TZ = /[zZ]|[+-]\d{2}:?\d{2}$/
const ISO_DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})/

/** Parse API ISO strings; naive values are treated as UTC. */
export function parseApiDatetime(iso) {
  if (!iso) return null
  const s = String(iso).trim()
  const normalized = ISO_HAS_TZ.test(s) ? s : `${s}Z`
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

function partsToDisplayDate(parts) {
  const day = parts.find((p) => p.type === 'day')?.value
  const month = parts.find((p) => p.type === 'month')?.value
  const year = parts.find((p) => p.type === 'year')?.value
  return day && month && year ? `${day}-${month}-${year}` : null
}

/** DD-MM-YYYY in IST for full datetime ISO strings. */
export function formatDateIN(iso) {
  const d = parseApiDatetime(iso)
  if (!d) return null
  return partsToDisplayDate(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: APP_TIMEZONE,
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).formatToParts(d),
  )
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

/** Combined Indian display: DD-MM-YYYY, 9:30 AM IST */
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

/** Today's calendar date in IST (YYYY-MM-DD) — for API inputs and comparisons only. */
export function todayIsoIST() {
  return new Date().toLocaleDateString('en-CA', { timeZone: APP_TIMEZONE })
}

/** Current billing month in IST (YYYY-MM). */
export function currentBillingMonthIST() {
  return todayIsoIST().slice(0, 7)
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

/**
 * Format YYYY-MM-DD API date as DD-MM-YYYY without timezone shift.
 * Use for scheduled_date, slot_date, and other date-only API fields.
 */
export function formatApiDateIN(dateStr) {
  if (!dateStr) return null
  const match = String(dateStr).trim().match(ISO_DATE_ONLY)
  if (!match) return null
  const [, y, m, d] = match
  return `${d}-${m}-${y}`
}

/** User-facing date with fallback (default em dash). */
export function formatDisplayDate(dateStr, fallback = '—') {
  return formatApiDateIN(dateStr) || fallback
}

/** DD-MM-YYYY · HH:MM for API date + wall-clock time. */
export function formatDisplayDateTime(dateStr, timeStr) {
  const date = formatApiDateIN(dateStr)
  if (!date) return null
  const time = timeStr ? String(timeStr).slice(0, 5) : null
  return time ? `${date} · ${time}` : date
}

/** DD-MM-YYYY · HH:MM–HH:MM */
export function formatDisplayDateTimeRange(dateStr, startTime, endTime) {
  const date = formatApiDateIN(dateStr)
  if (!date) return null
  const start = startTime ? String(startTime).slice(0, 5) : null
  const end = endTime ? String(endTime).slice(0, 5) : null
  if (start && end) return `${date} · ${start}–${end}`
  if (start) return `${date} · ${start}`
  return date
}

/** Friendly label: Wed, 28-05-2026 */
export function formatDisplayDateLabel(dateStr) {
  const formatted = formatApiDateIN(dateStr)
  if (!formatted) return ''
  const d = new Date(`${String(dateStr).slice(0, 10)}T12:00:00`)
  if (Number.isNaN(d.getTime())) return formatted
  const weekday = d.toLocaleDateString('en-IN', { weekday: 'short' })
  return `${weekday}, ${formatted}`
}

/** Date portion of a timestamp in DD-MM-YYYY (IST). */
export function formatTimestampDateIN(iso) {
  return formatDateIN(iso)
}

/** Inclusive API date range for filters and chips. */
export function formatDisplayDateRange(from, to) {
  if (!from && !to) return null
  if (from && to) return `${formatDisplayDate(from)} – ${formatDisplayDate(to)}`
  return formatDisplayDate(from || to)
}
