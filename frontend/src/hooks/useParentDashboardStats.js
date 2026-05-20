import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'

export function useParentDashboardStats() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cases, logs, hub, notifications] = await Promise.all([
        apiFetch('/api/v1/parent/cases'),
        apiFetch('/api/v1/parent/session-logs'),
        apiFetch('/api/v1/parent/reports/hub').catch(() => ({ iep: [] })),
        apiFetch('/api/v1/parent/notifications'),
      ])
      const pendingIep = (hub?.iep || []).filter((i) => i.status === 'pending').length
      const unread = (notifications || []).filter((n) => !n.is_read).length
      setStats({
        caseCount: (cases || []).length,
        sessionUpdates: (logs || []).length,
        pendingIep,
        unreadNotifications: unread,
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
