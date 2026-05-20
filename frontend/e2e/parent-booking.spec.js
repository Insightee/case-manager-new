import { test, expect } from '@playwright/test'

test.describe('Parent booking calendar', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill('parent@demo.com')
    await page.getByLabel(/password/i).fill('demo123')
    await page.getByRole('button', { name: /sign in|log in/i }).click()
    await expect(page).toHaveURL(/\/parent/)
  })

  test('book appointment page shows week calendar', async ({ page }) => {
    await page.getByRole('link', { name: /book appointment/i }).click()
    await expect(page.getByRole('heading', { name: /book appointment/i })).toBeVisible()
    await expect(page.getByText(/Today/)).toBeVisible()
    await expect(page.getByRole('columnheader', { name: /Time/i })).toBeVisible()
  })
})
