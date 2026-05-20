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
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const { access } = getTokens()
  if (access) headers.Authorization = `Bearer ${access}`

  let res
  try {
    res = await fetch(`${API_URL}${path}`, { ...options, headers })
  } catch {
    throw new Error(
      'Cannot reach the API. Run the backend (port 8000) and open the UI at http://localhost:5173 — not port 8000.',
    )
  }

  if (res.status === 401 && !path.includes('/auth/')) {
    const newAccess = await refreshAccess()
    if (newAccess) {
      headers.Authorization = `Bearer ${newAccess}`
      res = await fetch(`${API_URL}${path}`, { ...options, headers })
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
