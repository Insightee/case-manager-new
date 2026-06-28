/**
 * Clinical Brain — API + UI smoke for goal bank, strategy pool, review queue, parent-safe goals.
 */
import { test, expect } from '@playwright/test'
import { loginAdmin, loginParent } from './helpers/auth.js'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

/** @param {import('@playwright/test').APIRequestContext} request */
async function apiToken(request, email) {
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: 'demo123' },
  })
  expect(login.ok(), `Login failed for ${email}: ${await login.text()}`).toBeTruthy()
  return (await login.json()).access_token
}

/** @param {import('@playwright/test').APIRequestContext} request */
async function firstTherapistCaseId(request, token) {
  const res = await request.get(`${API}/api/v1/cases?page_size=1`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(res.ok()).toBeTruthy()
  const body = await res.json()
  const items = body.items ?? body
  expect(items.length).toBeGreaterThan(0)
  return items[0].id
}

/** @param {import('@playwright/test').APIRequestContext} request */
async function firstParentCaseId(request, token) {
  const res = await request.get(`${API}/api/v1/parent/cases`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(res.ok()).toBeTruthy()
  const cases = await res.json()
  expect(cases.length).toBeGreaterThan(0)
  return cases[0].id
}

test.describe('Clinical Brain API', () => {
  test('admin goal-bank and strategy-pool return organisation items', async ({ request }) => {
    const token = await apiToken(request, 'superadmin@demo.com')
    const headers = { Authorization: `Bearer ${token}` }

    const bank = await request.get(`${API}/api/v1/admin/goal-bank`, { headers })
    expect(bank.ok()).toBeTruthy()
    const bankBody = await bank.json()
    expect(Array.isArray(bankBody.items)).toBeTruthy()
    expect(bankBody.items.length).toBeGreaterThan(0)
    expect(bankBody.items[0]).toHaveProperty('label')

    const pool = await request.get(`${API}/api/v1/admin/strategy-pool`, { headers })
    expect(pool.ok()).toBeTruthy()
    const poolBody = await pool.json()
    expect(Array.isArray(poolBody.items)).toBeTruthy()
    expect(poolBody.items.length).toBeGreaterThan(0)
  })

  test('clinical review queue returns pending structure', async ({ request }) => {
    const token = await apiToken(request, 'superadmin@demo.com')
    const res = await request.get(`${API}/api/v1/admin/clinical-review-queue?tab=goal_candidates`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body).toHaveProperty('pending_goals')
    expect(body).toHaveProperty('pending_strategies')
    expect(Array.isArray(body.pending_goals)).toBeTruthy()
  })

  test('therapist goal-templates and strategy-pool-matches are case-scoped', async ({ request }) => {
    const token = await apiToken(request, 'therapist@demo.com')
    const headers = { Authorization: `Bearer ${token}` }
    const caseId = await firstTherapistCaseId(request, token)

    const templates = await request.get(`${API}/api/v1/cases/${caseId}/goal-templates`, { headers })
    expect(templates.ok()).toBeTruthy()
    expect(Array.isArray((await templates.json()).items)).toBeTruthy()

    const matches = await request.get(`${API}/api/v1/cases/${caseId}/strategy-pool-matches`, { headers })
    expect(matches.ok()).toBeTruthy()
    const matchBody = await matches.json()
    expect(Array.isArray(matchBody.items)).toBeTruthy()
    if (matchBody.items.length) {
      expect(matchBody.items[0]).toHaveProperty('evidence_label')
    }
  })

  test('parent-safe-goals returns allowlisted fields only', async ({ request }) => {
    const token = await apiToken(request, 'parent@demo.com')
    const headers = { Authorization: `Bearer ${token}` }
    const caseId = await firstParentCaseId(request, token)

    const res = await request.get(`${API}/api/v1/parent/cases/${caseId}/parent-safe-goals`, { headers })
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(Array.isArray(body.items)).toBeTruthy()
    for (const item of body.items) {
      expect(item).not.toHaveProperty('review_status')
      expect(item).not.toHaveProperty('evidence_count')
      expect(item).toHaveProperty('focus_area')
    }
  })

  test('check-language flags deficit framing', async ({ request }) => {
    const token = await apiToken(request, 'therapist@demo.com')
    const res = await request.post(`${API}/api/v1/clinical-brain/check-language`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { text: 'The child had a tantrum and poor eye contact.', context: 'session_note' },
    })
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    expect(body.safe_to_publish).toBe(false)
    expect(body.flagged_phrases.length).toBeGreaterThan(0)
  })

  test('therapist cannot access admin goal-bank', async ({ request }) => {
    const token = await apiToken(request, 'therapist@demo.com')
    const res = await request.get(`${API}/api/v1/admin/goal-bank`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.status()).toBe(403)
  })

  test('unified clinical review queue returns items array', async ({ request }) => {
    const token = await apiToken(request, 'superadmin@demo.com')
    const res = await request.get(`${API}/api/v1/clinical-brain/review-queue`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(res.ok()).toBeTruthy()
    expect(Array.isArray((await res.json()).items)).toBeTruthy()
  })

  test('strategy recommendation feedback list is case-scoped', async ({ request }) => {
    const therapistToken = await apiToken(request, 'therapist@demo.com')
    const headers = { Authorization: `Bearer ${therapistToken}` }
    const caseId = await firstTherapistCaseId(request, therapistToken)
    const res = await request.get(
      `${API}/api/v1/clinical-brain/cases/${caseId}/strategy-recommendation-feedback`,
      { headers },
    )
    expect(res.ok()).toBeTruthy()
    expect(Array.isArray((await res.json()).items)).toBeTruthy()
  })
})

test.describe('Clinical Brain UI', () => {
  test('admin goal bank loads from API', async ({ page }) => {
    await loginAdmin(page)
    const bankResponse = page.waitForResponse(
      (r) => r.url().includes('/api/v1/admin/goal-bank') && r.ok(),
    )
    await page.goto('/admin/goal-bank')
    const res = await bankResponse
    const body = await res.json()
    expect(body.items?.length).toBeGreaterThan(0)

    await expect(page.getByRole('heading', { name: 'Goal Bank' })).toBeVisible()
    await expect(page.getByText(body.items[0].label)).toBeVisible({ timeout: 15_000 })
  })

  test('admin strategy pool loads from API', async ({ page }) => {
    await loginAdmin(page)
    const poolResponse = page.waitForResponse(
      (r) => r.url().includes('/api/v1/admin/strategy-pool') && r.ok(),
    )
    await page.goto('/admin/strategy-pool')
    const res = await poolResponse
    const body = await res.json()
    expect(body.items?.length).toBeGreaterThan(0)

    await expect(page.getByRole('heading', { name: 'Strategy Pool' })).toBeVisible()
    await expect(page.getByText(body.items[0].label)).toBeVisible({ timeout: 15_000 })
  })

  test('clinical review queue loads pending candidates', async ({ page }) => {
    await loginAdmin(page)
    const queueResponse = page.waitForResponse(
      (r) => r.url().includes('/api/v1/admin/clinical-review-queue') && r.ok(),
    )
    await page.goto('/admin/clinical-review-queue')
    await queueResponse

    await expect(page.getByRole('heading', { name: 'Clinical review queue' })).toBeVisible()
    await expect(
      page.getByText(/No candidates awaiting review|Approve for case|Return with comment/).first(),
    ).toBeVisible({ timeout: 15_000 })
  })

  test('parent case goals tab loads parent-safe goals', async ({ page, request }) => {
    await loginParent(page)
    const token = await apiToken(request, 'parent@demo.com')
    const caseId = await firstParentCaseId(request, token)

    const goalsResponse = page.waitForResponse(
      (r) => r.url().includes('/parent-safe-goals') && r.ok(),
    )
    await page.goto(`/parent/cases/${caseId}`)
    await expect(page.getByRole('button', { name: 'Goals' })).toBeVisible()
    await page.getByRole('button', { name: 'Goals' }).click()
    const res = await goalsResponse
    const body = await res.json()

    await expect(
      page.getByText("Here are the current focus areas your child's team is supporting."),
    ).toBeVisible()
    if (body.items?.length) {
      await expect(page.getByRole('heading', { name: body.items[0].focus_area })).toBeVisible()
    } else {
      await expect(page.locator('.cb-parent-goal').first()).toBeVisible()
    }
  })
})
