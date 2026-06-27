import { test, expect } from '@playwright/test'
import { loginTherapist, navigateTherapist } from './helpers/auth.js'
import {
  endInProgressSessions,
  findTodayScheduledSessionId,
  openChildAbsenceForm,
  therapistApiToken,
} from './helpers/api.js'

const API_URL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

test.describe('Session patch UI', () => {
  test.beforeEach(async ({ request }) => {
    try {
      const token = await therapistApiToken(request, API_URL)
      await endInProgressSessions(request, token, API_URL)
    } catch {
      // API may not be up yet; individual tests will surface failures.
    }
  })

  test('child absence tab and composer are visible', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'Session Logs')

    await expect(page.getByRole('region', { name: 'Add or start session' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Child absence' })).toBeVisible()

    const hasForm = await openChildAbsenceForm(page)
    if (hasForm) {
      await expect(page.getByRole('button', { name: /Log child absent/i })).toBeVisible()
    } else {
      await expect(
        page.getByText(/No scheduled visit today for this client/i),
      ).toBeVisible()
    }
  })

  test('composer stays available while a live session is active', async ({ page, request }) => {
    const token = await therapistApiToken(request, API_URL)
    const sessionId = await findTodayScheduledSessionId(request, token, API_URL)
    test.skip(!sessionId, 'No SCHEDULED session today in seed data')

    const headers = { Authorization: `Bearer ${token}` }
    const start = await request.post(`${API_URL}/api/v1/sessions/${sessionId}/start`, {
      headers,
      data: {},
    })
    expect(start.ok()).toBeTruthy()

    try {
      await loginTherapist(page)
      await navigateTherapist(page, 'Session Logs')

      await expect(page.getByRole('heading', { name: 'Session in Progress' })).toBeVisible({ timeout: 15_000 })
      await expect(page.getByRole('button', { name: 'End Session' })).toBeVisible()
      await expect(page.getByText(/A session is in progress — end it above/i)).toBeVisible()
      await expect(page.getByRole('region', { name: 'Add or start session' })).toBeVisible()
      await expect(page.getByRole('tab', { name: 'Child absence' })).toBeVisible()
      await expect(page.getByRole('tab', { name: 'Start now' })).toBeDisabled()
      await expect(page.getByRole('tab', { name: 'Forgot to log' })).toBeDisabled()
    } finally {
      const cancel = await request.post(`${API_URL}/api/v1/sessions/${sessionId}/cancel`, { headers, data: {} })
      if (!cancel.ok()) {
        await request.post(`${API_URL}/api/v1/sessions/${sessionId}/end`, { headers, data: {} })
      }
    }
  })

  test('scheduling calendar renders without horizontal overflow', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'Scheduling')

    await expect(page.getByRole('heading', { name: 'Scheduling' })).toBeVisible()
    await expect(page.locator('table').first()).toBeVisible({ timeout: 15_000 })

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    )
    expect(overflow).toBe(false)
  })
})

test.describe('Session patch UI mobile', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test.beforeEach(async ({ request }) => {
    try {
      const token = await therapistApiToken(request, API_URL)
      await endInProgressSessions(request, token, API_URL)
    } catch {
      // API may not be up yet; individual tests will surface failures.
    }
  })

  test('child absence submit stays reachable on narrow viewport', async ({ page }) => {
    await loginTherapist(page)
    await navigateTherapist(page, 'Session Logs')
    const hasForm = await openChildAbsenceForm(page)
    if (hasForm) {
      await expect(page.getByRole('button', { name: /Log child absent/i })).toBeVisible()
    } else {
      test.skip(true, 'No client with a scheduled visit today in seed data')
    }
  })
})
