import { apiDownload } from './apiClient.js'

export function canDownloadApprovedSessionLog(log) {
  if (!log || log.id == null || Number(log.id) <= 0) return false
  const status = String(log.approval_status || '').toUpperCase()
  if (status === 'APPROVED') return true
  return log.parent_display_status === 'Reviewed'
}

export function sessionLogDownloadFilename(log) {
  const datePart = String(log?.scheduled_date || 'session').slice(0, 10)
  const namePart = String(log?.case_code || log?.child_name || `log_${log?.id || 'session'}`)
    .trim()
    .replace(/[^\w.\-]+/g, '_')
    .slice(0, 40)
  return `session_log_${namePart || 'log'}_${datePart}.pdf`
}

export function sessionLogDownloadPath(logId, { parent = false } = {}) {
  return parent
    ? `/api/v1/parent/session-logs/${logId}/download`
    : `/api/v1/daily-logs/${logId}/download`
}

export async function downloadApprovedSessionLog(log, { parent = false } = {}) {
  await apiDownload(sessionLogDownloadPath(log.id, { parent }), sessionLogDownloadFilename(log))
}
