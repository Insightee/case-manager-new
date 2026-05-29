const API_URL = import.meta.env.VITE_API_URL || ''

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
  if (import.meta.env.DEV) {
    globalThis.__insightcaseApiMetrics = requestMetrics
  }
}

export function getApiBaseUrl() {
  return API_URL
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
  if (import.meta.env.DEV) {
    const base = API_URL || 'http://localhost:8000 (via Vite proxy)'
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
  if (!refresh) return null
  const res = await fetchWithTimeout(`${API_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!res.ok) return null
  const data = await res.json()
  setTokens(data.access_token, data.refresh_token)
  return data.access_token
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
  const headers = { 'Content-Type': 'application/json', ...(fetchOptions.headers || {}) }
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`

  let res
  const startedAt = typeof performance !== 'undefined' ? performance.now() : Date.now()
  try {
    res = await fetchWithTimeout(`${API_URL}${url}`, { ...fetchOptions, headers }, timeoutMs)
  } catch (err) {
    const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
    recordApiMetric(path, elapsed, false)
    if (err?.message?.startsWith('Request timed out')) throw err
    const hostname = typeof window !== 'undefined' ? window.location.hostname : ''
    const onVercel = /\.vercel\.app$/i.test(hostname)
    const localDev = hostname === 'localhost' || hostname === '127.0.0.1'
    let hint
    if (!API_URL) {
      hint =
        'Cannot reach the API. Start the backend: cd backend && python3 -m uvicorn app.main:app --reload --port 8000 — then refresh this page.'
    } else if (onVercel) {
      const origin =
        typeof window !== 'undefined' && window.location?.origin ? window.location.origin : hostname
      hint =
        `Cannot reach the API at ${API_URL}. The API may be down, or this site origin (${origin}) may not be allowed by Railway CORS. ` +
        `Add ${origin} to Railway CORS_ORIGINS and FRONTEND_URL, redeploy the API, and confirm VITE_API_URL on Vercel (${API_URL}).`
    } else if (localDev) {
      hint = `Cannot reach the API at ${API_URL}. Start the backend (cd backend && python3 -m uvicorn app.main:app --reload --port 8000), or clear VITE_API_URL in frontend/.env.local and restart npm run dev to use the Vite proxy.`
    } else {
      hint = `Cannot reach the API at ${API_URL}. Check that the server is running and CORS allows this site.`
    }
    throw new Error(hint)
  }

  if (res.status === 401 && !path.includes('/auth/')) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetchWithTimeout(`${API_URL}${url}`, { ...fetchOptions, headers }, timeoutMs)
    }
    if (res.status === 401) {
      clearTokens()
      throw new Error('Session expired. Please log in again.')
    }
  }

  if (!res.ok) {
    const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startedAt
    recordApiMetric(path, elapsed, false)
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : res.statusText
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
    throw new Error(message || 'Request failed')
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
  return fetch(`${API_URL}${path}`, {
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

  let res = await fetchWithTimeout(`${API_URL}${path}`, { headers }, timeoutMs)
  if (res.status === 401 && access) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetchWithTimeout(`${API_URL}${path}`, { headers }, timeoutMs)
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const message =
      typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : res.statusText
    throw new Error(message || 'Request failed')
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
    res = await fetch(`${API_URL}${path}`, {
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
      res = await fetch(`${API_URL}${path}`, {
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

  let res = await fetchWithTimeout(`${API_URL}${path}`, { headers }, timeoutMs)
  if (res.status === 401 && access) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetchWithTimeout(`${API_URL}${path}`, { headers }, timeoutMs)
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
