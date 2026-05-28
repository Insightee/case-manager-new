import { test, expect } from '@playwright/test'
import { loginParent, sidebarLink } from './helpers/auth.js'

test.describe('Parent portal smoke', () => {
  test('dashboard and navigation load with API data', async ({ page }) => {
    await loginParent(page)

    await expect(page.getByRole('heading', { name: 'Family dashboard', level: 1 })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Family summary' })).toBeVisible()

    await sidebarLink(page, 'Session updates').click()
    await expect(page).toHaveURL(/\/parent\/session-logs/)
    await expect(page.getByRole('heading', { name: 'Session updates', level: 1 })).toBeVisible()

    await sidebarLink(page, 'Reports').click()
    await expect(page).toHaveURL(/\/parent\/reports/)
    await expect(page.getByRole('tab', { name: 'Monthly reports' })).toBeVisible()

    await sidebarLink(page, 'Billing').click()
    await expect(page).toHaveURL(/\/parent\/billing/)
  })

  test('session updates show approved logs when seeded', async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'Session updates').click()
    await expect(page.getByRole('heading', { name: 'Session updates', level: 1 })).toBeVisible()
    const logCard = page.locator('article').filter({ hasText: /Activities:|Goals:/ })
    await expect(logCard.first()).toBeVisible({ timeout: 15_000 })
  })

  test('case hub opens from dashboard', async ({ page }) => {
    await loginParent(page)
    const caseLink = page.locator('.log-list a').first()
    await expect(caseLink).toBeVisible()
    await caseLink.click()
    await expect(page).toHaveURL(/\/parent\/cases\/\d+/)
    await expect(page.getByRole('button', { name: 'Overview' })).toBeVisible()
  })

  test('monthly report detail opens from Reports hub', async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'Reports').click()
    const row = page.locator('.log-list button').first()
    await expect(row).toBeVisible({ timeout: 15_000 })
    await row.click()
    await expect(page.getByRole('dialog', { name: 'Report detail' })).toBeVisible()
  })

  test('IEP tab loads in Reports hub', async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'Reports').click()
    await page.getByRole('tab', { name: 'IEP plans' }).click()
    await expect(page).toHaveURL(/type=iep/)
    await expect(page.getByRole('heading', { name: 'IEP plans', level: 3 })).toBeVisible()
  })
})
