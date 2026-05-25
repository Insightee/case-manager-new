const API_URL = import.meta.env.VITE_API_URL || ''

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

async function refreshAccess() {
  const { refresh } = getTokens()
  if (!refresh) return null
  const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
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
  const { params, ...fetchOptions } = options
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
  try {
    res = await fetch(`${API_URL}${url}`, { ...fetchOptions, headers })
  } catch {
    const hint = API_URL
      ? `Cannot reach the API at ${API_URL}. Check that the server is running and CORS allows this site.`
      : 'Cannot reach the API. For local dev: run the backend on port 8000 and open http://localhost:5173. For Vercel: set VITE_API_URL to your deployed API.'
    throw new Error(hint)
  }

  if (res.status === 401 && !path.includes('/auth/')) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetch(`${API_URL}${url}`, { ...fetchOptions, headers })
    }
    if (res.status === 401) {
      clearTokens()
      throw new Error('Session expired. Please log in again.')
    }
  }

  if (!res.ok) {
    if (res.status === 502 || res.status === 503) {
      throw new Error(
        'Cannot reach the API server. Start the backend from the backend folder: uvicorn app.main:app --reload --port 8000',
      )
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const detail = err.detail
    const message = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : res.statusText
    throw new Error(message || 'Request failed')
  }

  if (res.status === 204) return null
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('text/csv')) return res.text()
  return res.json()
}

/** GET binary response with auth (for protected images). */
export async function apiFetchBlob(path) {
  const headers = {}
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`

  let res = await fetch(`${API_URL}${path}`, { headers })
  if (res.status === 401 && access) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetch(`${API_URL}${path}`, { headers })
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

export async function apiUpload(path, formData) {
  const headers = {}
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`
  let res = await fetch(`${API_URL}${path}`, { method: 'POST', headers, body: formData })
  if (res.status === 401 && access) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetch(`${API_URL}${path}`, { method: 'POST', headers, body: formData })
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
export async function apiDownload(path, filename) {
  const headers = {}
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`

  let res = await fetch(`${API_URL}${path}`, { headers })
  if (res.status === 401 && access) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetch(`${API_URL}${path}`, { headers })
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
