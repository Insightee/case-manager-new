import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'

export function useTherapistDashboardStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cases, sessions, logs, reports] = await Promise.all([
        apiFetch('/api/v1/cases?assigned=true'),
        apiFetch('/api/v1/sessions'),
        apiFetch('/api/v1/daily-logs'),
        apiFetch('/api/v1/reports/monthly'),
      ])
      const needsLog = (sessions || []).filter((s) => s.status === 'COMPLETED' && !s.has_daily_log).length
      const pendingLogs = (logs || []).filter((l) => l.approval_status === 'PENDING').length
      const draftReports = (reports || []).filter((r) => r.status === 'DRAFT' || r.status === 'REJECTED').length
      const underReview = (reports || []).filter((r) => r.status === 'UNDER_REVIEW').length
      setStats({
        caseCount: (cases || []).length,
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
