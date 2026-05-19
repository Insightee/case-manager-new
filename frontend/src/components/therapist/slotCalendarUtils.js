export const WEEKDAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
export const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export function pad2(n) {
  return String(n).padStart(2, '0')
}

export function dateStr(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

export function startOfWeek(d) {
  const copy = new Date(d)
  const day = copy.getDay()
  copy.setDate(copy.getDate() - day)
  copy.setHours(0, 0, 0, 0)
  return copy
}

export function addDays(d, n) {
  const copy = new Date(d)
  copy.setDate(copy.getDate() + n)
  return copy
}

export function weekDays(weekStart) {
  return Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))
}

/** Hour rows 9–17 for 30-min grid (18 slots per day column grouping by hour) */
export function defaultHourRows() {
  return Array.from({ length: 9 }, (_, i) => i + 9)
}

export const STATUS_STYLES = {
  AVAILABLE: 'bg-emerald-100 text-emerald-900 border-emerald-200',
  BOOKED: 'bg-blue-100 text-blue-900 border-blue-200',
  BLOCKED: 'bg-slate-200 text-slate-600 border-slate-300',
}
