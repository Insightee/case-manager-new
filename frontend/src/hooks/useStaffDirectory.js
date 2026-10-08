import { useCallback, useEffect, useState } from 'react'
import { apiFetch, onApiMutationSuccess, onTokenSync } from '../lib/apiClient.js'
import { STAFF_DIRECTORY_CACHE_MS } from '../lib/pollingIntervals.js'

export const STAFF_DIRECTORY_INVALIDATED_EVENT = 'insightcase:staff-directory-invalidated'

/** Requests that change who is in the staff directory (create / edit / deactivate / roles / profiles). */
const STAFF_MUTATION_PATH_RE = /^\/api\/v1\/(admin\/users|admin\/therapist|admin\/people|admin\/staff|admin\/invites|admin\/rbac|hr\/)/

/** @type {Map<string, { at: number, items: any[] }>} */
const cache = new Map()
/** @type {Map<string, Promise<any[]>>} */
const inflight = new Map()

export function isStaffMutationPath(path) {
  return STAFF_MUTATION_PATH_RE.test(String(path || '').split('?')[0])
}

export function invalidateStaffDirectoryCache() {
  cache.clear()
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function' && typeof Event === 'function') {
    window.dispatchEvent(new Event(STAFF_DIRECTORY_INVALIDATED_EVENT))
  }
}

// Any successful staff create / edit / deactivate through apiFetch clears the cache.
onApiMutationSuccess(({ path }) => {
  if (isStaffMutationPath(path)) invalidateStaffDirectoryCache()
})

// Never carry one account's directory into the next sign-in on the same tab.
onTokenSync((tokens) => {
  if (!tokens?.refresh) {
    cache.clear()
    inflight.clear()
  }
})

/**
 * @param {string} roles
 * @param {{ force?: boolean, now?: number, fetcher?: (path: string) => Promise<any> }} [opts]
 */
export async function fetchStaffDirectory(roles = '', opts = {}) {
  const key = roles || '*'
  const now = opts.now ?? Date.now()
  const hit = cache.get(key)
  if (!opts.force && hit && now - hit.at < STAFF_DIRECTORY_CACHE_MS) return hit.items
  if (!opts.force && inflight.has(key)) return inflight.get(key)
  const q = new URLSearchParams()
  if (roles) q.set('roles', roles)
  q.set('limit', '500')
  const path = `/api/v1/admin/users/directory?${q}`
  const fetcher = opts.fetcher || apiFetch
  const p = (async () => {
    try {
      const data = await fetcher(path)
      const items = Array.isArray(data) ? data : []
      cache.set(key, { at: opts.now ?? Date.now(), items })
      return items
    } finally {
      inflight.delete(key)
    }
  })()
  inflight.set(key, p)
  return p
}

/** Test-only. */
export function __resetStaffDirectoryCacheForTests() {
  cache.clear()
  inflight.clear()
}

/**
 * Staff directory for pickers. Cached for STAFF_DIRECTORY_CACHE_MS (30 min) and shared between
 * pickers; no reload on window focus. reload() always fetches fresh.
 */
export function useStaffDirectory({ roles = '', enabled = true } = {}) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(
    async (force = false) => {
      if (!enabled) return
      setLoading(true)
      try {
        setItems(await fetchStaffDirectory(roles, { force }))
      } catch {
        setItems([])
      } finally {
        setLoading(false)
      }
    },
    [roles, enabled],
  )

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!enabled) return undefined
    const onInvalidated = () => load(true)
    window.addEventListener(STAFF_DIRECTORY_INVALIDATED_EVENT, onInvalidated)
    return () => window.removeEventListener(STAFF_DIRECTORY_INVALIDATED_EVENT, onInvalidated)
  }, [load, enabled])

  const reload = useCallback(() => load(true), [load])
  return { items, loading, reload }
}
