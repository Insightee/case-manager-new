import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

// apiClient touches localStorage on import paths used below.
const store = {}
globalThis.localStorage ??= {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => {
    store[k] = String(v)
  },
  removeItem: (k) => {
    delete store[k]
  },
}

const {
  ADMIN_STATS_REFRESH_MS,
  FOCUS_REFETCH_MIN_AGE_MS,
  LIVE_FOCUS_REFETCH_MIN_AGE_MS,
  NOTIFICATION_POLL_MS,
  STAFF_DIRECTORY_CACHE_MS,
  USAGE_FLUSH_INTERVAL_MS,
} = await import('./pollingIntervals.js')
const { queryClient, queryKeys, QUERY_STALE_TIME_MS, refetchOnFocusIfOlderThan } = await import('./queryClient.js')
const { sendUsageQueue, bindUsageFlushOnLeave } = await import('./usageFlush.js')
const cache = await import('./therapistSessionLogCache.js')
const staff = await import('../hooks/useStaffDirectory.js')
const { apiFetch } = await import('./apiClient.js')

const MIN = 60 * 1000
const src = (p) => readFileSync(new URL(p, import.meta.url), 'utf8')

test('named intervals', () => {
  assert.equal(NOTIFICATION_POLL_MS, 10 * MIN)
  assert.equal(ADMIN_STATS_REFRESH_MS, 10 * MIN)
  assert.equal(FOCUS_REFETCH_MIN_AGE_MS, 10 * MIN)
  assert.equal(LIVE_FOCUS_REFETCH_MIN_AGE_MS, 2 * MIN)
  assert.equal(STAFF_DIRECTORY_CACHE_MS, 30 * MIN)
  assert.equal(USAGE_FLUSH_INTERVAL_MS, 30 * MIN)
})

test('intervals are wired where they are used (no leftover literals)', () => {
  assert.match(src('../components/shared/NotificationBell.jsx'), /setInterval\([\s\S]*NOTIFICATION_POLL_MS\)/)
  assert.doesNotMatch(src('../components/shared/NotificationBell.jsx'), /120000/)
  const stats = src('../components/admin-portal/AdminPlatformStatsPage.jsx')
  assert.equal((stats.match(/setInterval\(load(Stats|Activity), ADMIN_STATS_REFRESH_MS\)/g) || []).length, 2)
  assert.doesNotMatch(stats, /60_000/)
  assert.match(stats, /Last updated \$\{formatTimeIN12/)
  assert.match(src('../hooks/useAppUsageTracker.js'), /FLUSH_INTERVAL_MS = USAGE_FLUSH_INTERVAL_MS/)
  assert.doesNotMatch(src('../hooks/useStaffDirectory.js'), /'focus'/)
})

test('react-query: mount/navigation and reconnect unchanged; focus only for old data', () => {
  const q = queryClient.getDefaultOptions().queries
  assert.equal(QUERY_STALE_TIME_MS, 30_000)
  assert.equal(q.staleTime, 30_000)
  assert.equal(q.refetchOnMount, true)
  assert.equal(q.refetchOnReconnect, true)
  const now = 1_700_000_000_000
  const at = (ageMs) => ({ state: { dataUpdatedAt: now - ageMs } })
  const def = refetchOnFocusIfOlderThan(FOCUS_REFETCH_MIN_AGE_MS, () => now)
  assert.equal(def(at(31_000)), false, 'was true before (30 s stale)')
  assert.equal(def(at(9 * MIN)), false)
  assert.equal(def(at(10 * MIN)), true)
  assert.equal(def({ state: { dataUpdatedAt: 0 } }), true, 'no data yet still retries on focus')
  const live = refetchOnFocusIfOlderThan(LIVE_FOCUS_REFETCH_MIN_AGE_MS, () => now)
  assert.equal(live(at(90_000)), false)
  assert.equal(live(at(2 * MIN)), true)
  assert.equal(typeof q.refetchOnWindowFocus, 'function')
})

test('live screens keep the 2 min focus threshold', () => {
  const home = src('../hooks/useTherapistHome.js')
  assert.equal((home.match(/refetchOnWindowFocus: focusRefetchLive/g) || []).length, 2)
  assert.match(src('../hooks/useParentHome.js'), /refetchOnWindowFocus: focusRefetchLive/)
  assert.match(src('../components/daily-logs/DailyLogsPage.jsx'), /refetchOnWindowFocus: focusRefetchLive/)
  assert.match(src('../components/client-portal/ClientBookAppointmentPage.jsx'), /refetchOnWindowFocus: focusRefetchLive/)
})

test('regression: session marking and log save update the UI immediately (no focus needed)', () => {
  const uid = 7
  queryClient.setQueryData(queryKeys.therapistWorkspace, {
    active_session: null,
    upcoming: [{ id: 11, status: 'SCHEDULED' }, { id: 12, status: 'SCHEDULED' }],
    needs_log: [],
  })
  queryClient.setQueryData(queryKeys.therapistHome, { ok: true })
  queryClient.setQueryData(queryKeys.therapistDailyLogs(uid), [])

  cache.patchCachesAfterSessionStart({ id: 11, status: 'IN_PROGRESS' })
  let ws = queryClient.getQueryData(queryKeys.therapistWorkspace)
  assert.equal(ws.active_session.id, 11)
  assert.deepEqual(ws.upcoming.map((s) => s.id), [12])
  assert.equal(queryClient.getQueryState(queryKeys.therapistHome).isInvalidated, true)

  cache.patchCachesAfterSessionEnd({ id: 11, status: 'COMPLETED' })
  ws = queryClient.getQueryData(queryKeys.therapistWorkspace)
  assert.equal(ws.active_session, null)
  assert.deepEqual(ws.needs_log.map((s) => s.id), [11])

  cache.patchCachesAfterLogSave({ userId: uid, sessionId: 11, savedLog: { id: 501, session_id: 11 } })
  ws = queryClient.getQueryData(queryKeys.therapistWorkspace)
  assert.deepEqual(ws.needs_log, [])
  assert.deepEqual(queryClient.getQueryData(queryKeys.therapistDailyLogs(uid)).map((l) => l.id), [501])
  assert.equal(queryClient.getQueryState(queryKeys.therapistDailyLogs(uid)).isInvalidated, true)
  assert.equal(queryClient.getQueryState(queryKeys.therapistWorkspace).isInvalidated, true)
})

test('regression: schedule editing and saves outside react-query are untouched', () => {
  // Schedule editing (SlotEditSheet / calendars) reloads its own state via onSaved after each save.
  const sheet = src('../components/scheduling/SlotEditSheet.jsx')
  assert.match(sheet, /onSaved\?\.\(/)
  assert.doesNotMatch(sheet, /@tanstack\/react-query/)
})

test('unchanged: IEP / observation autosave (5 min) and login keep-alive (25 min)', () => {
  assert.match(src('../components/reports-engine/hooks/useIepReport.js'), /AUTO_SAVE_MS = 5 \* 60 \* 1000/)
  assert.match(src('../components/reports-engine/hooks/useObservationReport.js'), /AUTO_SAVE_MS = 5 \* 60 \* 1000/)
  assert.match(src('./apiClient.js'), /SESSION_KEEPALIVE_MS = 25 \* 60 \* 1000/)
  assert.match(src('../context/AuthContext.jsx'), /startSessionKeepAlive\(\)/)
  assert.match(src('../context/AuthContext.jsx'), /visibilitychange/)
})

test('usage tracker: queue persisted before send, kept on failure, sent chunks removed on success', async () => {
  let queue = [{ idempotency_key: 'old' }]
  const saved = []
  const io = {
    getQueue: () => queue,
    setQueue: (q) => {
      queue = q
    },
    save: (q) => saved.push(q.map((c) => c.idempotency_key)),
    maxQueue: 240,
  }
  const failed = await sendUsageQueue({ ...io, chunk: { idempotency_key: 'a' }, send: async () => {
    throw new Error('offline')
  } })
  assert.equal(failed, false)
  assert.deepEqual(queue.map((c) => c.idempotency_key), ['old', 'a'])
  assert.deepEqual(saved.at(-1), ['old', 'a'], 'persisted to storage')

  // A chunk queued while a send is in flight must survive that send's success.
  const ok = await sendUsageQueue({
    ...io,
    chunk: { idempotency_key: 'b' },
    send: async () => {
      queue = [...queue, { idempotency_key: 'late' }]
    },
  })
  assert.equal(ok, true)
  assert.deepEqual(queue.map((c) => c.idempotency_key), ['late'])
  assert.deepEqual(saved.at(-1), ['late'])
})

test('usage tracker: flushes with keepalive on tab hidden and page close', () => {
  const handlers = {}
  const target = (name) => ({
    addEventListener: (ev, fn) => {
      handlers[`${name}:${ev}`] = fn
    },
    removeEventListener: (ev) => {
      delete handlers[`${name}:${ev}`]
    },
  })
  const win = target('win')
  const doc = { ...target('doc'), visibilityState: 'visible' }
  const calls = []
  const unbind = bindUsageFlushOnLeave({ flush: (o) => calls.push(o), win, doc })
  handlers['doc:visibilitychange']()
  assert.equal(calls.length, 0, 'becoming visible does not flush')
  doc.visibilityState = 'hidden'
  handlers['doc:visibilitychange']()
  handlers['win:pagehide']()
  assert.deepEqual(calls, [
    { reason: 'hidden', useKeepalive: true },
    { reason: 'pagehide', useKeepalive: true },
  ])
  unbind()
  assert.equal(Object.keys(handlers).length, 0)
})

test('staff directory: cached 30 min, no refetch inside window, invalidated by staff mutations', async () => {
  staff.__resetStaffDirectoryCacheForTests()
  let calls = 0
  const fetcher = async () => {
    calls += 1
    return [{ id: calls }]
  }
  const t0 = 1_700_000_000_000
  await staff.fetchStaffDirectory('THERAPIST', { fetcher, now: t0 })
  await staff.fetchStaffDirectory('THERAPIST', { fetcher, now: t0 + 29 * MIN })
  assert.equal(calls, 1)
  await staff.fetchStaffDirectory('THERAPIST', { fetcher, now: t0 + 30 * MIN })
  assert.equal(calls, 2)

  for (const p of [
    '/api/v1/admin/users',
    '/api/v1/admin/users/12',
    '/api/v1/admin/users/bulk-status',
    '/api/v1/admin/therapists/invite',
    '/api/v1/admin/invites/bulk-revoke',
  ]) {
    assert.equal(staff.isStaffMutationPath(p), true, p)
  }
  assert.equal(staff.isStaffMutationPath('/api/v1/sessions/1/start'), false)

  // A successful DELETE (deactivate) through apiFetch clears the cache.
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  try {
    await apiFetch('/api/v1/admin/users/12', { method: 'DELETE' })
  } finally {
    globalThis.fetch = originalFetch
  }
  await staff.fetchStaffDirectory('THERAPIST', { fetcher, now: t0 + 31 * MIN })
  assert.equal(calls, 3, 'refetched after deactivate')
})
