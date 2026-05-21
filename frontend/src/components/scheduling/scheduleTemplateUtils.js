import { WEEKDAY_KEYS } from './slotCalendarUtils.js'

/** Normalize legacy { start, end } day config to { enabled, windows: [{ start, end }] }. */
export function normalizeDayConfig(day = {}) {
  if (Array.isArray(day.windows) && day.windows.length > 0) {
    return {
      enabled: !!day.enabled,
      windows: day.windows.map((w) => ({
        start: w.start || '09:00',
        end: w.end || '18:00',
      })),
    }
  }
  return {
    enabled: !!day.enabled,
    windows: [{ start: day.start || '09:00', end: day.end || '18:00' }],
  }
}

export function normalizeTemplateConfig(config) {
  if (!config) return null
  const days = {}
  for (const key of WEEKDAY_KEYS) {
    days[key] = normalizeDayConfig(config.days?.[key] || {})
  }
  return {
    ...config,
    slot_duration_minutes: config.slot_duration_minutes ?? 60,
    ongoing_enabled: !!config.ongoing_enabled,
    days,
  }
}

export function defaultDayWindows() {
  return [{ start: '09:00', end: '18:00' }]
}

export function addDayWindow(day) {
  const norm = normalizeDayConfig(day)
  const last = norm.windows[norm.windows.length - 1]
  const nextStart = last?.end || '13:00'
  return {
    ...norm,
    enabled: true,
    windows: [...norm.windows, { start: nextStart, end: '18:00' }],
  }
}

export function removeDayWindow(day, index) {
  const norm = normalizeDayConfig(day)
  const windows = norm.windows.filter((_, i) => i !== index)
  return {
    ...norm,
    windows: windows.length ? windows : defaultDayWindows(),
  }
}

export function updateDayWindow(day, index, field, value) {
  const norm = normalizeDayConfig(day)
  const windows = norm.windows.map((w, i) => (i === index ? { ...w, [field]: value } : w))
  return { ...norm, windows }
}

/** Ongoing availability: materialize this many weeks ahead (re-apply to extend). */
export const ONGOING_MATERIALIZE_WEEKS = 16
