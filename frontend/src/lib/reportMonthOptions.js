/** Canonical month labels for report drafts (e.g. "Aug 2026"). */

export function formatReportMonthLabel(date) {
  return date.toLocaleString('en-US', { month: 'short', year: 'numeric' })
}

export function buildReportMonthOptions(count = 14) {
  const options = []
  const anchor = new Date()
  anchor.setDate(1)
  for (let i = 0; i < count; i += 1) {
    const d = new Date(anchor.getFullYear(), anchor.getMonth() - i, 1)
    options.push(formatReportMonthLabel(d))
  }
  return options
}

export function normalizeReportMonthInput(value) {
  return String(value || '').trim()
}
