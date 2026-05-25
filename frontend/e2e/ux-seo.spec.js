import { test, expect } from '@playwright/test'

test.describe('UX, SEO, and accessibility review', () => {
  test('login page has document meta, landmarks, and form labels', async ({ page }) => {
    await page.goto('/login')

    await expect(page).toHaveTitle(/InsightCase/)
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    const description = page.locator('meta[name="description"]')
    await expect(description).toHaveAttribute('content', /InsightCase/i)

    const viewport = page.locator('meta[name="viewport"]')
    await expect(viewport).toHaveAttribute('content', /width=device-width/)

    await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeAttached()
    await expect(page.locator('#main-content')).toBeVisible()
    await expect(page.getByRole('tablist', { name: 'Select portal' })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Email' })).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  })

  test('portal shell exposes main landmark after sign-in', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('tab', { name: 'Therapist' }).click()
    await page.getByRole('textbox', { name: 'Email' }).fill('therapist@demo.com')
    await page.getByLabel('Password').fill('demo123')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await page.waitForURL(/\/therapist/)

    await expect(page).toHaveTitle(/Therapist Portal.*InsightCase/)
    await expect(page.locator('#main-content')).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Portal navigation' })).toBeVisible()
  })

  test('mobile viewport shows compact nav with menu for admin', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/login')
    await page.getByRole('tab', { name: 'Admin' }).click()
    await page.getByRole('textbox', { name: 'Email' }).fill('superadmin@demo.com')
    await page.getByLabel('Password').fill('demo123')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await page.waitForURL(/\/admin/)

    await expect(page.getByRole('navigation', { name: 'Quick navigation' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Menu' })).toBeVisible()

    await page.getByRole('button', { name: 'Menu' }).click()
    await expect(page.locator('#portal-nav-drawer.is-open')).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Portal navigation' })).toBeVisible()
  })
})
