import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'
import { useAuth } from '../context/AuthContext.jsx'

const ALL_OPTION = { value: '', label: 'All services' }

function modulesFromUser(user) {
  const mods = user?.modules || []
  const ids = new Set()
  const opts = []
  for (const m of mods) {
    for (const pid of m.case_product_modules || []) {
      if (!ids.has(pid)) {
        ids.add(pid)
        opts.push({ value: pid, label: m.label })
      }
    }
  }
  opts.sort((a, b) => a.label.localeCompare(b.label))
  return opts
}

/**
 * Clinical product_module options for filters and case creation.
 * Returns [{ value, label }] with leading "All services".
 */
export function useClinicalProductModules() {
  const { user } = useAuth()
  const [remote, setRemote] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const rows = await apiFetch('/api/v1/auth/clinical-product-modules')
      const opts = (rows || []).map((r) => ({ value: r.id, label: r.label }))
      setRemote(opts)
    } catch {
      setRemote(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load, user?.id])

  const options = useMemo(() => {
    const fromApi = remote ?? modulesFromUser(user)
    if (!fromApi.length) {
      return [ALL_OPTION]
    }
    return [ALL_OPTION, ...fromApi]
  }, [remote, user])

  const isEmpty = options.length <= 1 && !loading

  const labelByValue = useMemo(() => {
    const map = { '': ALL_OPTION.label }
    for (const o of options) {
      if (o.value) map[o.value] = o.label
    }
    return map
  }, [options])

  return { options, labelByValue, loading, isEmpty, reload: load }
}

export function clinicalProductModuleLabel(value, labelByValue) {
  if (!value) return labelByValue?.[''] || 'All services'
  return labelByValue?.[value] || value.replace(/_/g, ' ')
}
