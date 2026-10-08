import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  accessTokenNeedsRefresh,
  apiFetch,
  ensureAccessToken,
  getTokens,
  isPublicAuthPath,
  isTimeoutError,
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

/** Minimal JWT whose access token expired in 1970. */
const EXPIRED_ACCESS = 'eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjF9.expired'

describe('apiClient timeout helpers', () => {
  it('isTimeoutError matches dev and production timeout messages', () => {
    assert.equal(isTimeoutError(new Error('Request timed out after 30s.')), true)
    assert.equal(
      isTimeoutError(new Error('This is taking longer than expected (30s). Check your connection and try again.')),
      true,
    )
    assert.equal(isTimeoutError(new Error('Cannot reach the API through https://example.com')), false)
  })
})

describe('apiClient auth helpers', () => {
  it('accessTokenNeedsRefresh detects expired access tokens', () => {
    assert.equal(accessTokenNeedsRefresh(EXPIRED_ACCESS), true)
    assert.equal(accessTokenNeedsRefresh(null), true)
  })

  it('isPublicAuthPath excludes login and refresh only', () => {
    assert.equal(isPublicAuthPath('/api/v1/auth/login'), true)
    assert.equal(isPublicAuthPath('/api/v1/auth/refresh'), true)
    assert.equal(isPublicAuthPath('/api/v1/auth/me'), false)
  })
})

describe('apiClient interceptor', () => {
  beforeEach(() => {
    localStorage.clear()
    setTokens('initial_access', 'initial_refresh')
  })

  it('ensureAccessToken refreshes expired access tokens', async () => {
    setTokens(EXPIRED_ACCESS, 'initial_refresh')
    globalThis.fetch = async (url) => {
      if (url.includes('/auth/refresh')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: 'fresh_access', refresh_token: 'fresh_refresh' }),
        }
      }
      throw new Error(`Unexpected fetch: ${url}`)
    }

    const access = await ensureAccessToken()
    assert.equal(access, 'fresh_access')
    assert.equal(getTokens().access, 'fresh_access')
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

  it('refresh 200 retries /auth/me on 401', async () => {
    let callCount = 0
    globalThis.fetch = async (url, options) => {
      callCount++
      if (url.includes('/auth/refresh')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: 'new_access', refresh_token: 'new_refresh' }),
        }
      }
      if (callCount === 1) {
        return {
          ok: false,
          status: 401,
          statusText: 'Unauthorized',
          json: async () => ({ detail: 'Invalid token' }),
          headers: new Map(),
        }
      }
      assert.equal(options.headers.Authorization, 'Bearer new_access')
      return {
        ok: true,
        status: 200,
        json: async () => ({ id: 1, email: 'user@demo.com' }),
        headers: new Map(),
      }
    }

    const me = await apiFetch('/api/v1/auth/me')
    assert.equal(me.email, 'user@demo.com')
    assert.equal(getTokens().access, 'new_access')
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
