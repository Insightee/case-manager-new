/**
 * Session log Quick Evidence Card — structured V1.1 capture in therapist session log.
 */
import { test, expect } from '@playwright/test'
import { loginTherapist, sidebarLink } from './helpers/auth.js'
import { endInProgressSessions, ensureNeedsLogSession, therapistApiToken } from './helpers/api.js'

const API = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

async function openSessionLogForm(page, request) {
  const token = await therapistApiToken(request, API)
  await endInProgressSessions(request, token, API)
  const needsSessionId = await ensureNeedsLogSession(request, token, API)

  await loginTherapist(page)
  await sidebarLink(page, 'Session Logs').click()

  if (needsSessionId) {
    const completeLog = page.getByRole('button', { name: /Complete log|Continue log/i }).first()
    if (await completeLog.isVisible({ timeout: 10_000 }).catch(() => false)) {
      await completeLog.click()
      await expect(page.getByText(/Goals worked on today/i)).toBeVisible({ timeout: 15_000 })
      return true
    }
  }

  const startBtn = page.getByRole('button', { name: 'Start session' }).first()
  if (await startBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    await startBtn.click()
    await expect(page.getByRole('button', { name: /End [Ss]ession/i })).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button', { name: /End [Ss]ession/i }).click()
    await expect(page.getByText(/Goals worked on today|Complete Session Log/i).first()).toBeVisible({
      timeout: 15_000,
    })
    return true
  }

  return false
}

async function expandFirstGoal(page) {
  const quickEvidence = page.getByText('What helped participation today?')
  if (await quickEvidence.isVisible({ timeout: 3000 }).catch(() => false)) return

  const header = page.locator('.sl-goal-accordion__header').first()
  await expect(header).toBeVisible({ timeout: 15_000 })
  await header.click()
  await expect(quickEvidence).toBeVisible({ timeout: 10_000 })
}

function quickEvidenceSection(page) {
  return page.locator('.sl-quick-evidence')
}

test.describe('Session log Quick Evidence Card', () => {
  test.beforeEach(async ({ request }) => {
    try {
      const token = await therapistApiToken(request, API)
      await endInProgressSessions(request, token, API)
    } catch {
      // API may not be up yet; individual tests will surface failures.
    }
  })

  test('renders with conditional barrier and adaptation chips', async ({ page, request }) => {
    const opened = await openSessionLogForm(page, request)
    if (!opened) {
      test.skip(true, 'No startable session or pending log in seed data')
    }

    await expandFirstGoal(page)

    await quickEvidenceSection(page).getByRole('button', { name: 'Barrier present', exact: true }).click()
    await expect(quickEvidenceSection(page).getByRole('button', { name: 'Sensory load', exact: true })).toBeVisible()

    const addStrategy = page.getByRole('button', { name: '+ Add strategy' }).first()
    if (await addStrategy.isVisible()) {
      await addStrategy.click()
      const pick = page.locator('.sl-repo-picker__row').first()
      if (await pick.isVisible({ timeout: 5000 }).catch(() => false)) {
        await pick.click()
      }
    }

    const partly = page.getByRole('button', { name: 'Partly helpful', exact: true })
    if (await partly.isVisible()) {
      await partly.click()
      await expect(quickEvidenceSection(page).getByText('Adaptation type')).toBeVisible()
    } else {
      await quickEvidenceSection(page).getByRole('button', { name: 'Add adaptation' }).click()
      await expect(quickEvidenceSection(page).getByText('Adaptation type')).toBeVisible()
    }
  })

  test('saved V1.1 evidence appears in clinical evidence events API', async ({ page, request }) => {
    const opened = await openSessionLogForm(page, request)
    if (!opened) {
      test.skip(true, 'No startable session or pending log in seed data')
    }

    await expandFirstGoal(page)

    await quickEvidenceSection(page).getByRole('button', { name: 'Accepted', exact: true }).click()
    await quickEvidenceSection(page).getByRole('button', { name: 'Continue', exact: true }).click()

    const addStrategy = page.getByRole('button', { name: '+ Add strategy' }).first()
    if (await addStrategy.isVisible()) {
      await addStrategy.click()
      const pick = page.locator('.sl-repo-picker__row').first()
      if (await pick.isVisible({ timeout: 5000 }).catch(() => false)) {
        await pick.click()
        await page.getByRole('button', { name: 'Helpful', exact: true }).click()
      }
    }

    await page.getByLabel('Attendance').selectOption('PRESENT')
    await page.getByLabel('Session notes (internal)').fill('Quick evidence E2E internal notes')
    await page.getByLabel('Activities').fill('Play and transition practice')
    await page.getByLabel('Goals worked on').fill('Communication and participation goals')
    await page.getByLabel('Observations (internal)').fill('Engaged with visual supports')
    await page.getByLabel('Follow-ups').fill('Continue current plan')
    await page.getByLabel('Notes for family').fill('Good participation today')

    await page.getByRole('button', { name: /Submit log/i }).click()
    await expect(page.getByText(/submitted for review/i)).toBeVisible({ timeout: 20_000 })

    const token = await therapistApiToken(request, API)
    const headers = { Authorization: `Bearer ${token}` }

    const logsRes = await request.get(`${API}/api/v1/therapist/sessions/workspace`, { headers })
    const workspace = await logsRes.json()
    const recentLogId =
      workspace.recent_logs?.[0]?.daily_log_id || workspace.recent_logs?.[0]?.log_id || null

    let logId = recentLogId
    if (!logId) {
      const cases = await request.get(`${API}/api/v1/cases?page_size=1`, { headers })
      const caseId = (await cases.json()).items?.[0]?.id
      const month = new Date().toISOString().slice(0, 7)
      const monthEvents = await request.get(
        `${API}/api/v1/cases/${caseId}/clinical-evidence-events?month=${month}`,
        { headers },
      )
      const body = await monthEvents.json()
      logId = body.events?.[0]?.identity?.daily_log_id
    }

    expect(logId).toBeTruthy()
    const evRes = await request.get(`${API}/api/v1/daily-logs/${logId}/clinical-evidence-events`, {
      headers,
    })
    expect(evRes.ok()).toBeTruthy()
    const evBody = await evRes.json()
    const withChildResponse = (evBody.events || []).find(
      (e) => e.support_and_response?.child_response === 'accepted',
    )
    expect(withChildResponse).toBeTruthy()
    expect(withChildResponse.provenance?.field_provenance?.child_response).toBe('human_selected')
    expect(withChildResponse.visibility_and_governance?.parent_visible).toBe(false)
  })
})
