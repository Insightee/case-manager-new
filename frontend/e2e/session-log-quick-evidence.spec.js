/**
 * Voice-first session log — manual entry smoke (canonical editor).
 */
import { test, expect } from '@playwright/test'
import { loginTherapist, sidebarLink } from './helpers/auth.js'
import { endInProgressSessions, ensureNeedsLogSession, therapistApiToken } from './helpers/api.js'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

async function openVoiceDraft(page, request) {
  const token = await therapistApiToken(request, API)
  await endInProgressSessions(request, token, API)
  const needsSessionId = await ensureNeedsLogSession(request, token, API)

  await loginTherapist(page)
  await sidebarLink(page, 'Session Logs').click()

  if (needsSessionId) {
    const completeLog = page.getByRole('button', { name: /Complete log|Continue log/i }).first()
    if (await completeLog.isVisible({ timeout: 10_000 }).catch(() => false)) {
      await completeLog.click()
      const typeInstead = page.getByRole('button', { name: /Type instead/i })
      if (await typeInstead.isVisible({ timeout: 8000 }).catch(() => false)) {
        await typeInstead.click()
      }
      await expect(page.getByText(/What happened today/i)).toBeVisible({ timeout: 15_000 })
      return true
    }
  }

  const startBtn = page.getByRole('button', { name: 'Start session' }).first()
  if (await startBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    await startBtn.click()
    await expect(page.getByRole('button', { name: /End [Ss]ession/i })).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: /End [Ss]ession/i }).click()
    const typeInstead = page.getByRole('button', { name: /Type instead/i })
    if (await typeInstead.isVisible({ timeout: 8000 }).catch(() => false)) {
      await typeInstead.click()
    }
    await expect(page.getByText(/What happened today/i).first()).toBeVisible({ timeout: 15_000 })
    return true
  }

  return false
}

test.describe('Voice-first session log draft', () => {
  test.beforeEach(async ({ request }) => {
    try {
      const token = await therapistApiToken(request, API)
      await endInProgressSessions(request, token, API)
    } catch {
      // API may not be up yet
    }
  })

  test('manual entry draft shows story field and preview action', async ({ page, request }) => {
    const opened = await openVoiceDraft(page, request)
    if (!opened) {
      test.skip(true, 'No startable session or pending log in seed data')
    }

    await page.getByLabel(/What happened today/i).fill('Calm session with peer greeting practice.')
    await expect(page.getByRole('button', { name: /Preview/i })).toBeVisible()
  })
})
