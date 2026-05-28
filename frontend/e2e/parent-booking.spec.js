import { test, expect } from '@playwright/test'
import { loginParent, sidebarLink } from './helpers/auth.js'

test.describe('Parent session schedule', () => {
  test.beforeEach(async ({ page }) => {
    await loginParent(page)
  })

  test('session schedule page loads from navigation', async ({ page }) => {
    await sidebarLink(page, 'Session schedule').click()
    await expect(page).toHaveURL(/\/parent\/book/)
    await expect(page.getByRole('heading', { name: 'Session schedule', level: 1 })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Upcoming sessions' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Book a new therapy session' })).toBeVisible()
  })
})
