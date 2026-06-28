/**
 * Clinical AI foundation — disabled-safe responses.
 */
import { test, expect } from '@playwright/test'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

test.describe('Clinical AI foundation', () => {
  test('session-note improve returns safe payload when AI disabled', async ({ request }) => {
    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: 'therapist@demo.com', password: 'demo123' },
    })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }

    const res = await request.post(`${API}/api/v1/clinical-ai/session-note/improve`, {
      headers,
      data: { raw_note: 'Child engaged well with visual schedule today.' },
    })
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body.skipped === true || typeof body.draft_text === 'string').toBeTruthy()
  })

  test('parent-safe language check flags deficit framing', async ({ request }) => {
    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: 'therapist@demo.com', password: 'demo123' },
    })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }

    const res = await request.post(`${API}/api/v1/clinical-ai/language-check/parent-safe`, {
      headers,
      data: { text: 'The child had a tantrum and poor eye contact.' },
    })
    expect(res.ok()).toBeTruthy()
    expect((await res.json()).safe_to_publish).toBe(false)
  })
})
