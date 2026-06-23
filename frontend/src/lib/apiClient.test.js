import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  apiFetch,
  getTokens,
  setTokens,
} from './apiClient.js'

// Simple mock for localStorage
const storage = {}
globalThis.localStorage = {
  getItem: (key) => storage[key] || null,
  setItem: (key, value) => { storage[key] = String(value) },
  removeItem: (key) => { delete storage[key] },
  clear: () => { for (const k in storage) delete storage[k] }
}

describe('apiClient interceptor', () => {
  beforeEach(() => {
    localStorage.clear()
    setTokens('initial_access', 'initial_refresh')
  })

  it('refresh 200 retries original request', async () => {
    let callCount = 0
    globalThis.fetch = async (url, options) => {
      callCount++
      if (url.includes('/auth/refresh')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: 'new_access', refresh_token: 'new_refresh' })
        }
      }
      if (callCount === 1) {
        // First call fails with 401
        return {
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Token expired' }),
          headers: new Map()
        }
      }
      // Retry succeeds
      assert.equal(options.headers.Authorization, 'Bearer new_access')
      return {
        ok: true,
        status: 200,
        json: async () => ({ success: true }),
        headers: new Map()
      }
    }

    const res = await apiFetch('/api/v1/some-endpoint')
    assert.deepEqual(res, { success: true })
    assert.equal(getTokens().access, 'new_access')
    assert.equal(getTokens().refresh, 'new_refresh')
  })

  it('refresh 401 clears tokens', async () => {
    globalThis.fetch = async (url) => {
      if (url.includes('/auth/refresh')) {
        return {
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Invalid refresh token' }),
          headers: new Map()
        }
      }
      return {
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: async () => ({ detail: 'Token expired' }),
        headers: new Map()
      }
    }

    await assert.rejects(
      () => apiFetch('/api/v1/some-endpoint'),
      /Session expired/
    )
    assert.equal(getTokens().access, null)
    assert.equal(getTokens().refresh, null)
  })

  it('refresh 502 does not clear tokens', async () => {
    globalThis.fetch = async (url) => {
      if (url.includes('/auth/refresh')) {
        return {
          ok: false,
          status: 502,
          statusText: 'Bad Gateway',
          json: async () => ({ detail: 'Bad Gateway' }),
          headers: new Map()
        }
      }
      return {
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: async () => ({ detail: 'Token expired' }),
        headers: new Map()
      }
    }

    await assert.rejects(
      () => apiFetch('/api/v1/some-endpoint'),
      /Connection unstable/
    )
    // Tokens should NOT be cleared on server errors
    assert.equal(getTokens().access, 'initial_access')
    assert.equal(getTokens().refresh, 'initial_refresh')
  })
})
