/**
 * Strategy recommendation feedback — API smoke.
 */
import { test, expect } from '@playwright/test'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

async function token(request, email) {
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: 'demo123' },
  })
  expect(login.ok()).toBeTruthy()
  return (await login.json()).access_token
}

test.describe('Clinical Brain strategy feedback', () => {
  test('therapist can submit accepted feedback', async ({ request }) => {
    const therapistToken = await token(request, 'therapist@demo.com')
    const headers = { Authorization: `Bearer ${therapistToken}` }
    const cases = await request.get(`${API}/api/v1/cases?assigned=true&page_size=1`, { headers })
    const caseId = (await cases.json()).items[0].id

    const res = await request.post(
      `${API}/api/v1/clinical-brain/cases/${caseId}/strategy-recommendation-feedback`,
      {
        headers,
        data: {
          feedback_status: 'accepted',
          recommendation_source: 'library_match',
        },
      },
    )
    expect(res.ok()).toBeTruthy()
    expect((await res.json()).feedback_status).toBe('accepted')
  })

  test('needs_cm_input appears in unified review queue', async ({ request }) => {
    const therapistToken = await token(request, 'therapist@demo.com')
    const adminToken = await token(request, 'superadmin@demo.com')
    const th = { Authorization: `Bearer ${therapistToken}` }
    const admin = { Authorization: `Bearer ${adminToken}` }

    const cases = await request.get(`${API}/api/v1/cases?assigned=true&page_size=1`, { headers: th })
    const caseId = (await cases.json()).items[0].id

    await request.post(`${API}/api/v1/clinical-brain/cases/${caseId}/strategy-recommendation-feedback`, {
      headers: th,
      data: { feedback_status: 'needs_cm_input', dismissal_reason: 'E2E CM review' },
    })

    const queue = await request.get(`${API}/api/v1/clinical-brain/review-queue?item_type=recommendation_feedback`, {
      headers: admin,
    })
    expect(queue.ok()).toBeTruthy()
    const types = (await queue.json()).items.map((i) => i.item_type)
    expect(types).toContain('recommendation_feedback')
  })
})
