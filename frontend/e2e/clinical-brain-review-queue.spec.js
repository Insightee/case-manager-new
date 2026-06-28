/**
 * CM unified review queue actions — API smoke.
 */
import { test, expect } from '@playwright/test'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

async function adminHeaders(request) {
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: 'superadmin@demo.com', password: 'demo123' },
  })
  return { Authorization: `Bearer ${(await login.json()).access_token}` }
}

test.describe('Clinical Brain review queue actions', () => {
  test('admin can list unified queue', async ({ request }) => {
    const headers = await adminHeaders(request)
    const res = await request.get(`${API}/api/v1/clinical-brain/review-queue`, { headers })
    expect(res.ok()).toBeTruthy()
    expect(Array.isArray((await res.json()).items)).toBeTruthy()
  })

  test('admin can close a recommendation feedback item', async ({ request }) => {
    const headers = await adminHeaders(request)
    const list = await request.get(`${API}/api/v1/clinical-brain/review-queue?item_type=recommendation_feedback`, {
      headers,
    })
    const items = (await list.json()).items || []
    const item = items.find((i) => i.status === 'open' || i.status === 'pending')
    if (!item) {
      test.skip(true, 'No open recommendation_feedback queue item in seed')
    }

    const action = await request.post(`${API}/api/v1/clinical-brain/review-queue/${item.id}/action`, {
      headers,
      data: { action: 'close', reviewer_note: 'E2E close' },
    })
    expect(action.ok()).toBeTruthy()
  })
})
