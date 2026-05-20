import { test, expect } from '@playwright/test'
import { loginParent, sidebarLink } from './helpers/auth.js'

test.describe('Parent Reports hub', () => {
  test.beforeEach(async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'Reports').click()
    await expect(page).toHaveURL(/\/parent\/reports/)
    await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible()
  })

  test('switches between monthly reports and IEP tabs', async ({ page }) => {
    await page.getByRole('tab', { name: 'IEP plans' }).click()
    await expect(page).toHaveURL(/type=iep/)
    await page.getByRole('tab', { name: 'Monthly reports' }).click()
    await expect(page).not.toHaveURL(/type=iep/)
  })

  test('opens report detail sheet when list has items', async ({ page }) => {
    const row = page.locator('.log-list button').first()
    const count = await row.count()
    if (count === 0) {
      test.skip()
      return
    }
    await row.click()
    await expect(page.getByRole('dialog', { name: 'Report detail' })).toBeVisible()
    await page.getByRole('button', { name: 'Close' }).click()
    await expect(page.getByRole('dialog', { name: 'Report detail' })).toBeHidden()
  })
})
