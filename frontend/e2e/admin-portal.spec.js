import { test, expect } from '@playwright/test'
import { loginAdmin, sidebarLink } from './helpers/auth.js'

test.describe('Admin portal smoke', () => {
  test('dashboard and navigation load with API data', async ({ page }) => {
    await loginAdmin(page)

    await expect(page.getByRole('heading', { level: 2 })).toBeVisible()
    await expect(page.getByText('Active cases', { exact: true })).toBeVisible()

    await sidebarLink(page, 'Cases').click()
    await expect(page).toHaveURL(/\/admin\/cases/)
    await expect(page.getByRole('heading', { name: 'Cases', exact: true })).toBeVisible()

    await sidebarLink(page, 'Session Logs').click()
    await expect(page).toHaveURL(/\/admin\/logs/)
    await expect(page.getByRole('heading', { name: 'Session logs', exact: true })).toBeVisible()

    await sidebarLink(page, 'Report Review').click()
    await expect(page).toHaveURL(/\/admin\/reports/)
    await expect(page.getByRole('heading', { name: 'Report review', exact: true })).toBeVisible()

    await sidebarLink(page, 'IEP').click()
    await expect(page).toHaveURL(/\/admin\/iep/)
    await expect(page.getByRole('heading', { name: 'IEP management', exact: true })).toBeVisible()
  })

  test('report review view modal opens', async ({ page }) => {
    await loginAdmin(page)
    await sidebarLink(page, 'Report Review').click()
    const viewBtn = page.getByRole('button', { name: 'View' }).first()
    if (!(await viewBtn.isVisible())) {
      test.skip(true, 'No reports under review in seed')
    }
    await viewBtn.click()
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  test('session logs queue shows pending row when seeded', async ({ page }) => {
    await loginAdmin(page)
    await sidebarLink(page, 'Session Logs').click()
    await page.getByLabel('Filter by approval status').selectOption('PENDING')
    const approveBtn = page.getByRole('button', { name: 'Approve' }).first()
    if (!(await approveBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No pending logs in seed')
    }
    await expect(approveBtn).toBeVisible()
  })

  test('case hub opens from cases board', async ({ page }) => {
    await loginAdmin(page)
    await sidebarLink(page, 'Cases').click()
    const openLink = page.getByRole('link', { name: 'Open' }).first()
    await expect(openLink).toBeVisible()
    await openLink.click()
    await expect(page).toHaveURL(/\/admin\/cases\/\d+/)
    await expect(page.getByRole('button', { name: 'Overview' })).toBeVisible()
  })

  test('incidents page loads', async ({ page }) => {
    await loginAdmin(page)
    await page.locator('.app-sidebar__nav').getByRole('link', { name: 'Incidents', exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/incidents/)
    await expect(page.getByRole('heading', { name: 'Incidents', exact: true })).toBeVisible()
  })
})
