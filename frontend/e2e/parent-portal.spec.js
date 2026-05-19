import { test, expect } from '@playwright/test'
import { loginParent, sidebarLink } from './helpers/auth.js'

test.describe('Parent portal smoke', () => {
  test('dashboard and navigation load with API data', async ({ page }) => {
    await loginParent(page)

    await expect(page.getByRole('heading', { level: 2, name: 'Family dashboard' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Family summary' })).toBeVisible()

    await sidebarLink(page, 'Session updates').click()
    await expect(page).toHaveURL(/\/parent\/session-logs/)
    await expect(page.getByRole('heading', { name: 'Session updates' })).toBeVisible()

    await sidebarLink(page, 'Approved Reports').click()
    await expect(page).toHaveURL(/\/parent\/reports/)

    await sidebarLink(page, 'IEP Acknowledgement').click()
    await expect(page).toHaveURL(/\/parent\/iep/)

    await sidebarLink(page, 'Billing').click()
    await expect(page).toHaveURL(/\/parent\/billing/)
  })

  test('session updates show approved logs when seeded', async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'Session updates').click()
    await expect(page.getByRole('heading', { name: 'Session updates' })).toBeVisible()
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

  test('monthly report modal opens', async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'Approved Reports').click()
    const viewBtn = page.getByRole('button', { name: 'View report' }).first()
    await expect(viewBtn).toBeVisible({ timeout: 15_000 })
    await viewBtn.click()
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  test('IEP page loads', async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'IEP Acknowledgement').click()
    await expect(page.getByRole('heading', { name: 'IEP Status' })).toBeVisible()
  })
})
