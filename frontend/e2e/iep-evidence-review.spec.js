/**
 * IEP evidence review suggestions — API smoke.
 */
import { test, expect } from '@playwright/test'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

test.describe('IEP evidence review', () => {
  test('iep-evidence-review returns goal evidence structure', async ({ request }) => {
    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: 'therapist@demo.com', password: 'demo123' },
    })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
    const cases = await request.get(`${API}/api/v1/cases?assigned=true&page_size=1`, { headers })
    const caseId = (await cases.json()).items[0].id

    const res = await request.get(`${API}/api/v1/clinical-brain/cases/${caseId}/iep-evidence-review`, {
      headers,
    })
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body).toHaveProperty('goal_evidence')
    expect(body).toHaveProperty('review_period')
  })
})
