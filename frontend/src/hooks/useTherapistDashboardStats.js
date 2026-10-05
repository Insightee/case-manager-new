import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'

/** Use server aggregates from therapist home — never first-page list lengths. */
export function useTherapistDashboardStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const home = await apiFetch('/api/v1/therapist/home')
      const s = home?.stats || {}
      setStats({
        caseCount: s.case_count ?? 0,
        needsLog: s.needs_log ?? 0,
        pendingLogs: s.pending_logs ?? 0,
        draftReports: s.draft_reports ?? 0,
        underReview: s.under_review_reports ?? 0,
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
