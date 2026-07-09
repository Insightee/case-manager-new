import { generateMonthlyFromLogs } from './monthlyReportApi.js'

/**
 * @param {number} reportId
 * @param {'replace' | 'append'} mode
 */
export async function generateReportFromLogs(reportId, mode = 'replace') {
  return generateMonthlyFromLogs(reportId, mode)
}
