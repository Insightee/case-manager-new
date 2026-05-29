import { apiFetch } from './apiClient.js'

/**
 * @param {number} reportId
 * @param {'replace' | 'append'} mode
 */
export async function generateReportFromLogs(reportId, mode = 'replace') {
  return apiFetch(`/api/v1/reports/monthly/${reportId}/generate-from-logs`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}
