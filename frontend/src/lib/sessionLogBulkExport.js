import { apiDownload } from './apiClient.js'

export function confirmIncludeLogContent() {
  return window.confirm(
    'Include full log text in the spreadsheet?\n\nOK — include content\nCancel — summary only (therapist, date, time, and status)',
  )
}

export function buildCaseSessionLogExportQuery({
  viewMode,
  selectedMonth,
  selectedDate,
  statusFilter,
  attendanceFilter,
  year,
  includeContent,
}) {
  const params = new URLSearchParams()
  params.set('view_mode', viewMode || 'all')
  if (viewMode === 'month' && selectedMonth) params.set('month', selectedMonth)
  if (viewMode === 'day' && selectedDate) params.set('date', selectedDate)
  if (year) params.set('year', String(year))
  if (statusFilter) params.set('status', statusFilter)
  if (attendanceFilter) params.set('attendance', attendanceFilter)
  if (includeContent) params.set('include_content', 'true')
  return params.toString()
}

export function caseSessionLogExportPath(caseId, { parent = false, query = '' } = {}) {
  if (parent) {
    const prefix = `/api/v1/parent/session-logs/export/xlsx?case_id=${encodeURIComponent(caseId)}`
    return query ? `${prefix}&${query}` : prefix
  }
  const qs = query ? `?${query}` : ''
  return `/api/v1/cases/${encodeURIComponent(caseId)}/session-logs/export/xlsx${qs}`
}

export function caseSessionLogExportFilename({ caseCode, periodLabel } = {}) {
  const casePart = String(caseCode || 'case')
    .trim()
    .replace(/[^\w.\-]+/g, '_')
    .slice(0, 40)
  const periodPart = String(periodLabel || 'export')
    .trim()
    .replace(/[^\w.\-]+/g, '_')
    .slice(0, 40)
  return `session_logs_${casePart || 'case'}_${periodPart || 'export'}.xlsx`
}

export function caseSessionLogExportPeriodLabel({ viewMode, selectedMonth, selectedDate, year }) {
  if (viewMode === 'day' && selectedDate) return selectedDate
  if (viewMode === 'month' && selectedMonth) return selectedMonth
  if (year) return String(year)
  return 'all'
}

export async function downloadCaseSessionLogExport({
  caseId,
  parent = false,
  viewMode,
  selectedMonth,
  selectedDate,
  statusFilter,
  attendanceFilter,
  year,
  caseCode,
  includeContent = false,
}) {
  const query = buildCaseSessionLogExportQuery({
    viewMode,
    selectedMonth,
    selectedDate,
    statusFilter,
    attendanceFilter,
    year,
    includeContent,
  })
  const path = caseSessionLogExportPath(caseId, { parent, query })
  const filename = caseSessionLogExportFilename({
    caseCode,
    periodLabel: caseSessionLogExportPeriodLabel({ viewMode, selectedMonth, selectedDate, year }),
  })
  await apiDownload(path, filename)
}
