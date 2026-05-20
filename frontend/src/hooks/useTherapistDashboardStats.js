import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'
import { unwrapList } from '../lib/listApi.js'

export function useTherapistDashboardStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cases, sessions, logs, reports] = await Promise.all([
        apiFetch('/api/v1/cases?assigned=true&page_size=100'),
        apiFetch('/api/v1/sessions?page_size=100'),
        apiFetch('/api/v1/daily-logs'),
        apiFetch('/api/v1/reports/monthly?page_size=100'),
      ])
      const caseRows = unwrapList(cases)
      const sessionRows = unwrapList(sessions)
      const logRows = unwrapList(logs)
      const reportRows = unwrapList(reports)
      const needsLog = sessionRows.filter((s) => s.status === 'COMPLETED' && !s.has_daily_log).length
      const pendingLogs = logRows.filter((l) => l.approval_status === 'PENDING').length
      const draftReports = reportRows.filter((r) => r.status === 'DRAFT' || r.status === 'REJECTED').length
      const underReview = reportRows.filter((r) => r.status === 'UNDER_REVIEW').length
      setStats({
        caseCount: caseRows.length,
        needsLog,
        pendingLogs,
        draftReports,
        underReview,
      })
    } catch {
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { stats, loading, reload: load }
}
