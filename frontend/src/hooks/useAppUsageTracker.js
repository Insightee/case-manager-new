import { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, apiPostKeepalive } from '../lib/apiClient.js'

const STORAGE_KEY = 'insightcase:usage:chunks:v1'
const MAX_QUEUE = 240
const FLUSH_INTERVAL_MS = 15 * 60 * 1000
const IDLE_MS = 60 * 1000

function nowIso() {
  return new Date().toISOString()
}

function newSessionId(userId) {
  return globalThis.crypto?.randomUUID?.() || `sess-${Date.now()}-${userId}`
}

function loadQueue() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.slice(-MAX_QUEUE) : []
  } catch {
    return []
  }
}

function saveQueue(queue) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue.slice(-MAX_QUEUE)))
  } catch {
    // Ignore storage quota issues; in-memory queue still works for this session.
  }
}

function createChunk({ sessionId, portal, route, activeSeconds, idleSeconds, hiddenSeconds, startedAt, endedAt, reason }) {
  return {
    session_id: sessionId,
    portal,
    route,
    active_seconds: Math.max(0, activeSeconds | 0),
    idle_seconds: Math.max(0, idleSeconds | 0),
    hidden_seconds: Math.max(0, hiddenSeconds | 0),
    started_at: startedAt || null,
    ended_at: endedAt || nowIso(),
    idempotency_key: `${sessionId}:${startedAt || 'na'}:${endedAt || nowIso()}:${activeSeconds}:${idleSeconds}:${hiddenSeconds}:${reason}`,
  }
}

export function useAppUsageTracker({ enabled, userId, portal, routePath }) {
  const [activeElapsedSeconds, setActiveElapsedSeconds] = useState(0)
  const [syncState, setSyncState] = useState('idle')
  const queueRef = useRef(loadQueue())
  const countersRef = useRef({ active: 0, idle: 0, hidden: 0 })
  const metaRef = useRef({
    sessionId: userId ? newSessionId(userId) : null,
    chunkStartedAt: nowIso(),
    lastInteractionAt: Date.now(),
  })

  const flush = useMemo(
    () => async ({ reason = 'interval', useKeepalive = false } = {}) => {
      if (!enabled || !userId || !metaRef.current.sessionId) return
      const c = countersRef.current
      if (c.active <= 0 && c.idle <= 0 && c.hidden <= 0 && queueRef.current.length === 0) return

      const chunk = createChunk({
        sessionId: metaRef.current.sessionId,
        portal,
        route: routePath,
        activeSeconds: c.active,
        idleSeconds: c.idle,
        hiddenSeconds: c.hidden,
        startedAt: metaRef.current.chunkStartedAt,
        endedAt: nowIso(),
        reason,
      })
      countersRef.current = { active: 0, idle: 0, hidden: 0 }
      metaRef.current.chunkStartedAt = nowIso()

      const nextQueue = [...queueRef.current, chunk].slice(-MAX_QUEUE)
      queueRef.current = nextQueue
      saveQueue(nextQueue)
      setSyncState('retry_pending')

      const payload = { chunks: queueRef.current }
      try {
        setSyncState('syncing')
        const res = useKeepalive
          ? await apiPostKeepalive('/api/v1/auth/activity/batch', payload)
          : await apiFetch('/api/v1/auth/activity/batch', { method: 'POST', body: JSON.stringify(payload) })
        if (useKeepalive && !res?.ok) throw new Error('Keepalive sync failed')
        queueRef.current = []
        saveQueue([])
        setSyncState('synced')
      } catch {
        setSyncState('retry_pending')
      }
    },
    [enabled, userId, portal, routePath],
  )

  useEffect(() => {
    if (!enabled || !userId) {
      setActiveElapsedSeconds(0)
      setSyncState('idle')
      return undefined
    }

    metaRef.current.sessionId = metaRef.current.sessionId || newSessionId(userId)
    metaRef.current.chunkStartedAt = metaRef.current.chunkStartedAt || nowIso()
    metaRef.current.lastInteractionAt = Date.now()

    const markInteraction = () => {
      metaRef.current.lastInteractionAt = Date.now()
    }

    const interactionEvents = ['pointerdown', 'mousemove', 'keydown', 'scroll', 'touchstart']
    for (const evt of interactionEvents) window.addEventListener(evt, markInteraction, { passive: true })
    window.addEventListener('focus', markInteraction)
    document.addEventListener('visibilitychange', markInteraction)

    const tickInterval = window.setInterval(() => {
      const now = Date.now()
      const isVisible = document.visibilityState === 'visible'
      const isFocused = typeof document.hasFocus === 'function' ? document.hasFocus() : true
      if (!isVisible) {
        countersRef.current.hidden += 1
        return
      }
      if (!isFocused || now - metaRef.current.lastInteractionAt >= IDLE_MS) {
        countersRef.current.idle += 1
        return
      }
      countersRef.current.active += 1
      setActiveElapsedSeconds((v) => v + 1)
    }, 1000)

    const periodicFlush = window.setInterval(() => {
      void flush({ reason: 'interval' })
    }, FLUSH_INTERVAL_MS)

    const onPageHide = () => {
      void flush({ reason: 'pagehide', useKeepalive: true })
    }
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        void flush({ reason: 'hidden', useKeepalive: true })
      }
    }

    window.addEventListener('pagehide', onPageHide)
    document.addEventListener('visibilitychange', onVisibility)

    // Boot retry for unsynced queue.
    if (queueRef.current.length > 0) {
      void flush({ reason: 'boot_retry' })
    }

    return () => {
      window.clearInterval(tickInterval)
      window.clearInterval(periodicFlush)
      for (const evt of interactionEvents) window.removeEventListener(evt, markInteraction)
      window.removeEventListener('focus', markInteraction)
      document.removeEventListener('visibilitychange', markInteraction)
      window.removeEventListener('pagehide', onPageHide)
      document.removeEventListener('visibilitychange', onVisibility)
      void flush({ reason: 'cleanup', useKeepalive: true })
    }
  }, [enabled, userId, flush])

  return {
    activeElapsedSeconds,
    syncState,
    flushNow: (reason = 'manual') => flush({ reason }),
  }
}
