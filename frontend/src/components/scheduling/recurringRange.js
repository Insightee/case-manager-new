import { WEEKDAY_KEYS } from './slotCalendarUtils.js'
import { todayIsoIST } from '../../lib/datetime.js'

export { todayIsoIST }

const WEEKDAY_NAMES = {
  mon: 'Monday',
  tue: 'Tuesday',
  wed: 'Wednesday',
  thu: 'Thursday',
  fri: 'Friday',
  sat: 'Saturday',
  sun: 'Sunday',
}

const SKIP_REASONS = {
  leave: 'therapist leave',
  already_booked: 'already booked for this case',
  other_case: 'booked for another case',
  unavailable: 'that time is not open',
}

/** Add calendar days to a YYYY-MM-DD string. Uses UTC date parts so IST midnight cannot shift the day. */
export function addDaysIso(iso, days) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d + Number(days)))
  const yy = dt.getUTCFullYear()
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(dt.getUTCDate()).padStart(2, '0')
  return `${yy}-${mm}-${dd}`
}

/** Monday-first key for a calendar date. Matches Python date.weekday(). */
export function weekdayKeyFromIso(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number)
  const utcDay = new Date(Date.UTC(y, m - 1, d)).getUTCDay()
  const index = utcDay === 0 ? 6 : utcDay - 1
  return WEEKDAY_KEYS[index]
}

export function expandWeekdayDates(weekdays, fromIso, toIso) {
  if (!fromIso || !toIso || toIso < fromIso) return []
  const keys = new Set(weekdays)
  const out = []
  let cursor = String(fromIso).slice(0, 10)
  const end = String(toIso).slice(0, 10)
  while (cursor <= end) {
    if (keys.has(weekdayKeyFromIso(cursor))) out.push(cursor)
    cursor = addDaysIso(cursor, 1)
  }
  return out
}

export function nWeeksRange(startIso, weeks) {
  const count = Math.min(52, Math.max(1, Number(weeks) || 1))
  const from = String(startIso).slice(0, 10)
  return { from, to: addDaysIso(from, count * 7 - 1) }
}

/** Selected weekdays that fall earlier in the Monday-start week than the start date. */
export function earlierSelectedWeekdays(weekdays, startIso) {
  if (!startIso) return []
  const startIndex = WEEKDAY_KEYS.indexOf(weekdayKeyFromIso(startIso))
  return (weekdays || []).filter((key) => WEEKDAY_KEYS.indexOf(key) >= 0 && WEEKDAY_KEYS.indexOf(key) < startIndex)
}

export function includeEarlierSelectedDays(startIso, weekdays) {
  const earlier = earlierSelectedWeekdays(weekdays, startIso)
  if (!earlier.length) return startIso
  const startIndex = WEEKDAY_KEYS.indexOf(weekdayKeyFromIso(startIso))
  const earliest = Math.min(...earlier.map((key) => WEEKDAY_KEYS.indexOf(key)))
  return addDaysIso(startIso, earliest - startIndex)
}

export function earlierWeekdayMessage(weekdays, startIso) {
  const earlier = earlierSelectedWeekdays(weekdays, startIso)
  if (!earlier.length) return ''
  const names = earlier.map((key) => WEEKDAY_NAMES[key] || key)
  const label = names.length === 1 ? names[0] : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
  const verb = names.length === 1 ? 'is' : 'are'
  return `${label} ${verb} before the start date, so ${names.length === 1 ? 'that day is' : 'those days are'} not in this booking yet. Move the start date back to include them.`
}

export function formatSkipMessage(booked, skipped) {
  if (!skipped?.length) return ''
  const lines = skipped.slice(0, 6).map((row) => {
    const reason = SKIP_REASONS[row.reason] || row.reason || 'not booked'
    return `${row.date} (${reason})`
  })
  const more = skipped.length > 6 ? ` ${skipped.length - 6} more dates were left as they are.` : ''
  const count = Number(booked) || 0
  const lead = count
    ? `Booked ${count} session${count === 1 ? '' : 's'}.`
    : 'No sessions were booked for that range.'
  return `${lead} These dates stayed as they are: ${lines.join('; ')}.${more}`
}
