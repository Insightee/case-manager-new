const CACHE_KEY = 'insightcase:schedule-cache:v1'
const TTL_MS = 2 * 60 * 1000

const memoryCache = new Map()
const cacheMetrics = { hits: 0, misses: 0, sets: 0 }

function publishMetrics() {
  if (import.meta.env.DEV) {
    globalThis.__insightcaseScheduleCacheMetrics = { ...cacheMetrics }
  }
}

function keyFor({ apiPrefix, therapistId, caseId, fromDate, toDate }) {
  return [apiPrefix, therapistId || 'self', caseId || 'none', fromDate, toDate].join('|')
}

function readDisk() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeDisk(obj) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(obj))
  } catch {
    // best effort
  }
}

export function getScheduleCache(params) {
  const key = keyFor(params)
  const mem = memoryCache.get(key)
  if (mem) {
    cacheMetrics.hits += 1
    publishMetrics()
    return mem
  }
  const disk = readDisk()
  const value = disk[key]
  if (value) {
    memoryCache.set(key, value)
    cacheMetrics.hits += 1
    publishMetrics()
    return value
  }
  cacheMetrics.misses += 1
  publishMetrics()
  return null
}

export function setScheduleCache(params, calendar) {
  const key = keyFor(params)
  const payload = { calendar, cachedAt: Date.now() }
  memoryCache.set(key, payload)
  cacheMetrics.sets += 1
  publishMetrics()
  const disk = readDisk()
  disk[key] = payload
  // Trim old entries opportunistically.
  const cutoff = Date.now() - 24 * 60 * 60 * 1000
  for (const k of Object.keys(disk)) {
    if ((disk[k]?.cachedAt || 0) < cutoff) delete disk[k]
  }
  writeDisk(disk)
}

export function isScheduleCacheFresh(entry) {
  if (!entry) return false
  return Date.now() - (entry.cachedAt || 0) <= TTL_MS
}

/** Drop cached calendar payloads so a new booking shows immediately. */
export function clearScheduleCache() {
  memoryCache.clear()
  try {
    localStorage.removeItem(CACHE_KEY)
  } catch {
    // best effort
  }
}
