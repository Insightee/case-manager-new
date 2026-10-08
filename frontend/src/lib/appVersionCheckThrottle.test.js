import assert from 'node:assert/strict'
import test from 'node:test'

import {
  __resetVersionCheckStateForTests,
  __resetVersionSchedulerForTests,
  canCheckVersionNow,
  fetchRemoteVersionMeta,
  msUntilNextVersionCheck,
  readCachedRemoteVersionMeta,
  startVersionCheckScheduler,
  VERSION_CHECK_INTERVAL_MS,
  VERSION_CHECK_TS_KEY,
} from './appVersionUpdate.js'

const HOUR = 60 * 60 * 1000

function memoryStorage() {
  const map = new Map()
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  }
}

function fakeFetch(label = 'i1009', buildId = 'abc123') {
  const calls = []
  const impl = async (url) => {
    calls.push(url)
    return { ok: true, json: async () => ({ releaseLabel: label, buildId }) }
  }
  return { impl, calls }
}

test('interval is a single 12h constant', () => {
  assert.equal(VERSION_CHECK_INTERVAL_MS, 12 * HOUR)
})

test('first check runs; no second check within 12h; check again after 12h', async () => {
  __resetVersionCheckStateForTests()
  const storage = memoryStorage()
  const { impl, calls } = fakeFetch()
  const t0 = 1_700_000_000_000

  const first = await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: impl, now: t0 })
  assert.equal(first.releaseLabel, 'i1009')
  assert.equal(calls.length, 1)

  for (const later of [t0 + 1000, t0 + 5 * 60 * 1000, t0 + 6 * HOUR, t0 + 12 * HOUR - 1]) {
    const cached = await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: impl, now: later })
    assert.equal(cached.releaseLabel, 'i1009', 'cached result returned without a request')
  }
  assert.equal(calls.length, 1, 'no extra requests inside the 12h window')

  await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: impl, now: t0 + 12 * HOUR })
  assert.equal(calls.length, 2, 'checks again once 12h have passed')
})

test('shared across tabs and portals through localStorage', async () => {
  const storage = memoryStorage() // one device-wide localStorage
  const t0 = 1_700_000_000_000
  const tabA = fakeFetch('i1009')
  __resetVersionCheckStateForTests()
  await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: tabA.impl, now: t0 })

  // A new tab (fresh module state) in another portal, 2h later, sees the stored timestamp + result.
  __resetVersionCheckStateForTests()
  const tabB = fakeFetch('i1010')
  const seen = await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: tabB.impl, now: t0 + 2 * HOUR })
  assert.equal(tabB.calls.length, 0)
  assert.equal(seen.releaseLabel, 'i1009')
  assert.equal(readCachedRemoteVersionMeta({ storage }).releaseLabel, 'i1009')
  assert.equal(canCheckVersionNow({ storage, now: t0 + 2 * HOUR }), false)
  assert.equal(msUntilNextVersionCheck({ storage, now: t0 + 2 * HOUR }), 10 * HOUR)
})

test('concurrent callers in one tab share a single request', async () => {
  __resetVersionCheckStateForTests()
  const storage = memoryStorage()
  const { impl, calls } = fakeFetch()
  const now = 1_700_000_000_000
  const results = await Promise.all([
    fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: impl, now }),
    fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: impl, now }),
    fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: impl, now }),
  ])
  assert.equal(calls.length, 1)
  assert.ok(results.every((r) => r?.releaseLabel === 'i1009'))
})

test('failed request still waits 12h (no retry storm) and keeps the last good result', async () => {
  __resetVersionCheckStateForTests()
  const storage = memoryStorage()
  const t0 = 1_700_000_000_000
  await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: fakeFetch('i1008').impl, now: t0 })
  let failing = 0
  const broken = async () => {
    failing += 1
    throw new TypeError('Failed to fetch')
  }
  const r1 = await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: broken, now: t0 + 12 * HOUR })
  const r2 = await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: broken, now: t0 + 13 * HOUR })
  assert.equal(failing, 1)
  assert.equal(r1.releaseLabel, 'i1008')
  assert.equal(r2.releaseLabel, 'i1008')
})

test('clock moved back counts as due; junk labels are ignored', async () => {
  __resetVersionCheckStateForTests()
  const storage = memoryStorage()
  storage.setItem(VERSION_CHECK_TS_KEY, String(2_000_000_000_000))
  assert.equal(canCheckVersionNow({ storage, now: 1_700_000_000_000 }), true)
  const { impl } = fakeFetch('<script>')
  const r = await fetchRemoteVersionMeta({ enabled: true, storage, fetchImpl: impl, now: 1_700_000_000_000 })
  assert.equal(r, null)
  assert.equal(readCachedRemoteVersionMeta({ storage }), null)
})

test('disabled (dev builds) never fetches', async () => {
  __resetVersionCheckStateForTests()
  const { impl, calls } = fakeFetch()
  assert.equal(await fetchRemoteVersionMeta({ enabled: false, storage: memoryStorage(), fetchImpl: impl }), null)
  assert.equal(calls.length, 0)
})

test('scheduler starts once per tab and never waits less than a minute', async () => {
  __resetVersionCheckStateForTests()
  __resetVersionSchedulerForTests()
  const waits = []
  const setTimer = (_fn, ms) => {
    waits.push(ms)
    return 1
  }
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => ({ ok: false })
  try {
    startVersionCheckScheduler({ force: true, setTimer })
    startVersionCheckScheduler({ force: true, setTimer })
    await new Promise((r) => setTimeout(r, 10))
    assert.equal(waits.length, 1)
    assert.ok(waits[0] >= 60_000)
  } finally {
    globalThis.fetch = originalFetch
    __resetVersionSchedulerForTests()
  }
})
