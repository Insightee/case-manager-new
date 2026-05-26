import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'

export function useStaffDirectory({ roles = '', enabled = true } = {}) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    try {
      const q = new URLSearchParams()
      if (roles) q.set('roles', roles)
      q.set('limit', '500')
      const path = `/api/v1/admin/users/directory${q.toString() ? `?${q}` : ''}`
      const data = await apiFetch(path)
      setItems(Array.isArray(data) ? data : [])
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [roles, enabled])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!enabled) return undefined
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [load, enabled])

  return { items, loading, reload: load }
}
