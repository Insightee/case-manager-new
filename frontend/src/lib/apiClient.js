/** Production UI hosts that proxy /api on the same origin (see vercel.json rewrites). */
const SAME_ORIGIN_API_HOSTS = /^((www\.)?insighte\.org|[a-z0-9-]+\.vercel\.app)$/i

const getEnv = (key) => {
  if (typeof import.meta !== 'undefined' && import.meta.env) {
    return import.meta.env[key]
  }
  return undefined
}

const isDev = () => {
  if (typeof import.meta !== 'undefined' && import.meta.env) {
    return import.meta.env.DEV
  }
  return false
}

function parseApiErrorDetail(detail, statusText = '') {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const joined = detail.map((d) => d?.msg || d?.message || JSON.stringify(d)).filter(Boolean).join(', ')
    if (joined) return joined
  }
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) return detail.message
    if (typeof detail.detail === 'string' && detail.detail.trim()) return detail.detail
  }
  return statusText || ''
}

function resolveApiBaseUrl() {
  const configured = (getEnv('VITE_API_URL') || '').replace(/\/$/, '')
  if (typeof window === 'undefined') return configured
  const host = window.location.hostname
  // Apex insighte.org 308-redirects to www before /api rewrites; use www explicitly to avoid
  // redirect stripping PATCH bodies / Authorization on cross-host hops.
  if (host === 'insighte.org') {
    return 'https://www.insighte.org'
  }
  if (SAME_ORIGIN_API_HOSTS.test(host)) {
    return ''
  }
  return configured
}

function apiBase() {
  return resolveApiBaseUrl()
}

const DEFAULT_TIMEOUT_MS = 30_000
const requestMetrics = {
  total: 0,
  byPath: {},
  slow: 0,
  failures: 0,
}

function recordApiMetric(path, elapsedMs, ok) {
  requestMetrics.total += 1
  requestMetrics.byPath[path] = (requestMetrics.byPath[path] || 0) + 1
  if (elapsedMs >= 1200) requestMetrics.slow += 1
  if (!ok) requestMetrics.failures += 1
  if (isDev()) {
    globalThis.__insightcaseApiMetrics = requestMetrics
  }
}

// #region agent log
const BILLING_PATH_RE = /\/(billing|invoices|client-billing|finance|payout)/i
function debugBillingApiLog(location, message, data, hypothesisId = 'E') {
  if (!BILLING_PATH_RE.test(data?.path || '')) return
  fetch('http://127.0.0.1:7284/ingest/6bb4b18a-59b3-4583-8388-f541aa2607d1', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '3264f0' },
    body: JSON.stringify({
      sessionId: '3264f0',
      location,
      message,
      data,
      hypothesisId,
      timestamp: Date.now(),
      runId: data?.runId || 'browser',
    }),
  }).catch(() => {})
}
// #endregion

export function getApiBaseUrl() {
  return resolveApiBaseUrl()
}

export function getApiMetricsSnapshot() {
  return {
    total: requestMetrics.total,
    byPath: { ...requestMetrics.byPath },
    slow: requestMetrics.slow,
    failures: requestMetrics.failures,
  }
}

export function getTokens() {
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  }
}

export function setTokens(access, refresh) {
  localStorage.setItem('access_token', access)
  if (refresh) localStorage.setItem('refresh_token', refresh)
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

function timeoutErrorMessage(timeoutMs = DEFAULT_TIMEOUT_MS) {
  const secs = Math.round(timeoutMs / 1000)
  if (isDev()) {
    const base = apiBase() || 'http://localhost:8000 (via Vite proxy)'
    return `Request timed out after ${secs}s. The API may be down or an operation is stuck — check GET /health and start the backend: cd backend && python3 -m uvicorn app.main:app --reload --port 8000 (${base}).`
  }
  return `This is taking longer than expected (${secs}s). Check your connection and try again.`
}

export async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = timeoutMs > 0 ? new AbortController() : null
  const timer =
    controller &&
    setTimeout(() => {
      controller.abort()
    }, timeoutMs)
  try {
    return await fetch(url, {
      ...options,
      signal: controller?.signal,
    })
  } catch (err) {
    if (err?.name === 'AbortError') {
      throw new Error(timeoutErrorMessage(timeoutMs))
    }
    throw err
  } finally {
    if (timer) clearTimeout(timer)
  }
}

async function refreshAccess() {
  const { refresh } = getTokens()
  if (!refresh) {
    const err = new Error('No refresh token')
    err.isAuthError = true
    throw err
  }
  try {
    const res = await fetchWithTimeout(`${apiBase()}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (res.status === 401 || res.status === 403) {
      const err = new Error('Session expired')
      err.isAuthError = true
      err.status = res.status
      throw err
    }
    if (!res.ok) {
      const err = new Error(`Server returned ${res.status}`)
      err.isServerError = true
      err.status = res.status
      throw err
    }
    const data = await res.json()
    setTokens(data.access_token, data.refresh_token)
    return data.access_token
  } catch (err) {
    if (err.isAuthError || err.status === 401 || err.status === 403) {
      throw err
    }
    err.isNetworkOrServerError = true
    throw err
  }
}

/** True when the session should be cleared (auth failure, not network noise). */
export function isAuthSessionError(err) {
  if (err?.status === 401 || err?.status === 403) return true
  const msg = String(err?.message || '')
  return (
    /session expired/i.test(msg) ||
    /invalid refresh/i.test(msg) ||
    /refresh token revoked/i.test(msg) ||
    /invalid refresh token/i.test(msg)
  )
}

/** Refresh access token when missing; returns current or new access token, or null. */
export async function ensureAccessToken() {
  const { access, refresh } = getTokens()
  if (access) return access
  if (!refresh) return null
  try {
    return await refreshAccess()
  } catch {
    return null
  }
}

/** Silently rotate access token when a refresh token exists (e.g. tab refocus). */
export async function tryRefreshSession() {
  const { refresh } = getTokens()
  if (!refresh) return null
  try {
    return await refreshAccess()
  } catch {
    return null
  }
}

export async function apiFetch(path, options = {}) {
  const { params, timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options
  let url = path
  if (params && typeof params === 'object') {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.set(k, String(v))
    }
    const q = qs.toString()
    if (q) url = `${path}${path.includes('?') ? '&' : '?'}${q}`
  }
  const headers = { ...(fetchOptions.headers || {}) }
  if (!(fetchOptions.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`

  let res
  const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
  try {
    res = await fetchWithTimeout(`${getApiBaseUrl()}${url}`, { ...fetchOptions, headers }, timeoutMs)
  } catch (err) {
    const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
    recordApiMetric(path, elapsed, false)
    // #region agent log
    debugBillingApiLog('apiClient.js:apiFetch', 'billing fetch network error', {
      path,
      ok: false,
      error: err?.message?.slice(0, 120),
    })
    // #endregion
    if (err?.message?.startsWith('Request timed out')) throw err
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      const offlineErr = new Error('You appear offline. Check your connection and try again.')
      offlineErr.isConnectionError = true
      throw offlineErr
    }
    const hostname = typeof window !== 'undefined' ? window.location.hostname : ''
    const onVercel = /\.vercel\.app$/i.test(hostname)
    const onInsighte = SAME_ORIGIN_API_HOSTS.test(hostname)
    const localDev = hostname === 'localhost' || hostname === '127.0.0.1'
    let hint
    if (!getApiBaseUrl() && localDev) {
      hint =
        'Cannot reach the API. Start the backend: cd backend && python3 -m uvicorn app.main:app --reload --port 8000 — then refresh this page.'
    } else if (onInsighte || onVercel) {
      const origin =
        typeof window !== 'undefined' && window.location?.origin ? window.location.origin : hostname
      hint =
        `Cannot reach the API through ${origin}. Redeploy the frontend (vercel.json /api proxy) or check GET /health on the Railway API.`
    } else if (localDev) {
      hint = `Cannot reach the API at ${getEnv('VITE_API_URL') || '(vite proxy)'}. Start the backend (cd backend && python3 -m uvicorn app.main:app --reload --port 8000), or clear VITE_API_URL in frontend/.env.local and restart npm run dev.`
    } else {
      const configured = getEnv('VITE_API_URL') || getApiBaseUrl() || '(not set)'
      hint = `Cannot reach the API at ${configured}. Check that the server is running and CORS allows this site.`
    }
    throw new Error(hint)
  }

  if (res.status === 401 && !path.includes('/auth/')) {
    try {
      const newAccess = await refreshAccess()
      if (newAccess) {
        headers.Authorization = `Bearer ${newAccess}`
        res = await fetchWithTimeout(`${getApiBaseUrl()}${url}`, { ...fetchOptions, headers }, timeoutMs)
      } else {
        clearTokens()
        throw new Error('Session expired. Please log in again.')
      }
    } catch (refreshErr) {
      if (refreshErr.isAuthError || refreshErr.status === 401 || refreshErr.status === 403) {
        clearTokens()
        throw new Error('Session expired. Please log in again.')
      }
      const netErr = new Error('Connection unstable. You are still logged in, but we cannot reach the server.')
      netErr.isConnectionError = true
      throw netErr
    }
  }

  if (!res.ok) {
    const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
    recordApiMetric(path, elapsed, false)
    // #region agent log
    debugBillingApiLog('apiClient.js:apiFetch', 'billing fetch http error', {
      path,
      ok: false,
      status: res.status,
    })
    // #endregion
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    let message = parseApiErrorDetail(detail, res.statusText)
    if (!message && typeof err === 'object' && err !== null) {
      message = parseApiErrorDetail(err.message, res.statusText)
    }
    if (res.status === 502 || res.status === 503) {
      if (message && message !== res.statusText && message !== 'Bad Gateway' && message !== 'Service Unavailable') {
        throw new Error(message)
      }
      const localDev =
        typeof window !== 'undefined' &&
        (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
      throw new Error(
        localDev
          ? 'API is not responding. In a terminal run: cd backend && python3 -m uvicorn app.main:app --reload --port 8000 — then refresh this page.'
          : 'API is not responding. Check that the backend service is running and VITE_API_URL points to it.',
      )
    }
    const apiError = new Error(message || `Request failed (${res.status})`)
    apiError.status = res.status
    apiError.detail = detail
    throw apiError
  }

  if (res.status === 204) return null
  const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
  recordApiMetric(path, elapsed, true)
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('text/csv')) return res.text()
  return res.json()
}

export function apiPostKeepalive(path, payload) {
  const headers = { 'Content-Type': 'application/json' }
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`
  const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
  return fetch(`${apiBase()}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    keepalive: true,
  })
    .then((res) => {
      const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
      recordApiMetric(path, elapsed, res.ok)
      return res
    })
    .catch((err) => {
      const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
      recordApiMetric(path, elapsed, false)
      throw err
    })
}

/** GET binary response with auth (for protected images). */
export async function apiFetchBlob(path, { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const headers = {}
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`

  let res = await fetchWithTimeout(`${apiBase()}${path}`, { headers }, timeoutMs)
  if (res.status === 401 && access) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetchWithTimeout(`${apiBase()}${path}`, { headers }, timeoutMs)
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const message = parseApiErrorDetail(detail, res.statusText)
    throw new Error(message || `Request failed (${res.status})`)
  }
  return res.blob()
}

export async function apiUpload(path, formData, { timeoutMs = 60000 } = {}) {
  const headers = {}
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`
  const controller = timeoutMs > 0 ? new AbortController() : null
  const timer =
    controller &&
    setTimeout(() => {
      controller.abort()
    }, timeoutMs)
  let res
  try {
    res = await fetch(`${apiBase()}${path}`, {
      method: 'POST',
      headers,
      body: formData,
      signal: controller?.signal,
    })
  } catch (err) {
    if (err?.name === 'AbortError') {
      throw new Error('Upload timed out. Try fewer or smaller files.')
    }
    throw err
  } finally {
    if (timer) clearTimeout(timer)
  }
  if (res.status === 401 && !path.includes('/auth/login') && !path.includes('/auth/refresh')) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetch(`${apiBase()}${path}`, {
        method: 'POST',
        headers,
        body: formData,
        signal: controller?.signal,
      })
    }
    if (res.status === 401) {
      clearTokens()
      throw new Error('Session expired. Please log in again.')
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : 'Upload failed'
    throw new Error(message)
  }
  return res.json()
}

/** Authenticated download; triggers browser save via temporary object URL. */
export async function apiDownload(path, filename, { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const headers = {}
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`

  let res = await fetchWithTimeout(`${apiBase()}${path}`, { headers }, timeoutMs)
  if (res.status === 401 && access) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetchWithTimeout(`${apiBase()}${path}`, { headers }, timeoutMs)
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Download failed')
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'download'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const TICKET_ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024
export const TICKET_ATTACHMENT_MAX_FILES = 3
