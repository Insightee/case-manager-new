/**
 * Parent-safe goals + parent goal inputs — API smoke.
 */
import { test, expect } from '@playwright/test'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

test.describe('Parent-safe goals', () => {
  test('parent-safe-goals omits internal fields', async ({ request }) => {
    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: 'parent@demo.com', password: 'demo123' },
    })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
    const cases = await request.get(`${API}/api/v1/parent/cases`, { headers })
    const caseId = (await cases.json())[0].id

    const res = await request.get(`${API}/api/v1/parent/cases/${caseId}/parent-safe-goals`, { headers })
    expect(res.ok()).toBeTruthy()
    for (const item of (await res.json()).items || []) {
      expect(item).not.toHaveProperty('review_status')
      expect(item).not.toHaveProperty('evidence_count')
    }
  })

  test('parent can submit goal input', async ({ request }) => {
    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: 'parent@demo.com', password: 'demo123' },
    })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
    const cases = await request.get(`${API}/api/v1/parent/cases`, { headers })
    const caseId = (await cases.json())[0].id

    const res = await request.post(`${API}/api/v1/parent/cases/${caseId}/goal-inputs`, {
      headers,
      data: { goal_ref: 'peer_play', input_type: 'see_at_home', comment: 'E2E parent input' },
    })
    expect(res.ok()).toBeTruthy()
    expect((await res.json()).input_type).toBe('see_at_home')
  })
})
