/**
 * Monthly evidence compiler — API smoke.
 */
import { test, expect } from '@playwright/test'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

test.describe('Monthly evidence compiler', () => {
  test('compile and fetch evidence snapshot', async ({ request }) => {
    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: 'therapist@demo.com', password: 'demo123' },
    })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
    const cases = await request.get(`${API}/api/v1/cases?assigned=true&page_size=1`, { headers })
    const caseId = (await cases.json()).items[0].id
    const month = '2099-08'

    const start = await request.post(`${API}/api/v1/cases/${caseId}/reports/monthly/start?month=${month}`, {
      headers,
    })
    expect(start.ok(), await start.text()).toBeTruthy()
    const reportId = (await start.json()).report_id

    const compile = await request.post(
      `${API}/api/v1/reports/${reportId}/monthly/compile-evidence?force=true`,
      { headers },
    )
    expect(compile.ok(), await compile.text()).toBeTruthy()
    const body = await compile.json()
    expect(body.month).toBe(month)
    expect(body).toHaveProperty('source_hash')

    const snap = await request.get(`${API}/api/v1/reports/${reportId}/evidence-snapshot`, { headers })
    expect(snap.ok()).toBeTruthy()
    expect((await snap.json()).month).toBe(month)
  })
})
