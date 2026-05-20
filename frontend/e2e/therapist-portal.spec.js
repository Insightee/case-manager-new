import { test, expect } from '@playwright/test'
import { loginTherapist, sidebarLink } from './helpers/auth.js'

test.describe('Therapist portal smoke', () => {
  test('dashboard, navigation, and core pages load with API data', async ({ page }) => {
    await loginTherapist(page)

    await expect(page.getByRole('heading', { level: 2 })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Work summary' })).toBeVisible()

    await sidebarLink(page, 'Session Logs').click()
    await expect(page).toHaveURL(/\/therapist\/logs/)
    await expect(page.getByRole('heading', { name: 'Session Logs' })).toBeVisible()

    await sidebarLink(page, 'My Cases').click()
    await expect(page).toHaveURL(/\/therapist\/cases/)
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Case summary' })).toBeVisible()

    await sidebarLink(page, 'Monthly Reports').click()
    await expect(page).toHaveURL(/\/therapist\/reports/)
    await expect(page.getByRole('heading', { name: 'Monthly Reports' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Report pipeline overview' })).toBeVisible()

    await sidebarLink(page, 'Invoices').click()
    await expect(page).toHaveURL(/\/therapist\/invoices/)
    await expect(page.getByRole('heading', { name: 'Invoices', exact: true })).toBeVisible()
  })

  test('my cases detail opens from board', async ({ page }) => {
    await loginTherapist(page)
    await sidebarLink(page, 'My Cases').click()
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()

    const caseLink = page.getByRole('link', { name: 'View case' }).first()
    await expect(caseLink).toBeVisible()
    await caseLink.click()
    await expect(page).toHaveURL(/\/therapist\/cases\/\d+/)
    await expect(page.getByRole('button', { name: 'Overview' })).toBeVisible()

    await page.goBack()
    await expect(page.getByRole('heading', { name: 'My Cases' })).toBeVisible()
    const sessionLogLink = page.locator('.ic-card').getByRole('link', { name: 'Session log', exact: true }).first()
    await sessionLogLink.click()
    await expect(page).toHaveURL(/\/therapist\/cases\/\d+\?tab=sessions/)
    await expect(page.getByRole('button', { name: 'Sessions & logs' })).toBeVisible()
  })

  test('session log flow: start, end, and submit form', async ({ page }) => {
    await loginTherapist(page)
    await sidebarLink(page, 'Session Logs').click()

    const startBtn = page.getByRole('button', { name: 'Start session' }).first()
    if (await startBtn.isVisible()) {
      await startBtn.click()
      await expect(page.getByText('Session in progress')).toBeVisible({ timeout: 15_000 })
      await page.getByRole('button', { name: 'End session' }).click()
      await expect(page.getByRole('heading', { name: 'Submit session log' })).toBeVisible({ timeout: 15_000 })
      await page.getByLabel('Attendance').selectOption('PRESENT')
      await page.getByLabel('Session notes (internal)').fill('Playwright E2E session notes')
      await page.getByLabel('Activities').fill('Play activities')
      await page.getByLabel('Goals worked on').fill('Communication goals')
      await page.getByLabel('Observations (internal)').fill('Engaged throughout')
      await page.getByLabel('Follow-ups').fill('Continue plan')
      await page.getByLabel('Notes for family').fill('Good session today')
      await page.getByRole('button', { name: 'Submit log' }).click()
      await expect(page.getByText(/submitted for review/i)).toBeVisible({ timeout: 15_000 })
    } else {
      const needsLog = page.getByRole('button', { name: /needs log/i }).first()
      if (await needsLog.isVisible()) {
        await needsLog.click()
        await expect(page.getByRole('heading', { name: 'Submit session log' })).toBeVisible()
      } else {
        test.skip(true, 'No startable session or pending log in seed data')
      }
    }
  })

  test('monthly report draft modal opens', async ({ page }) => {
    await loginTherapist(page)
    await sidebarLink(page, 'Monthly Reports').click()
    await page.getByRole('button', { name: '+ Create Draft' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('heading', { name: /new monthly report draft/i })).toBeVisible()
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('dialog')).toBeHidden()
  })
})
