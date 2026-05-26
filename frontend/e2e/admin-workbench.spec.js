import { test, expect } from '@playwright/test'

async function loginCaseManager(page) {
  await page.goto('/login')
  await page.getByRole('tab', { name: 'Admin' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill('casemanager@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/admin/)
}

test.describe('Admin workbench (My caseload)', () => {
  test('workbench loads sections for case manager', async ({ page }) => {
    await loginCaseManager(page)
    await page.locator('.app-sidebar__nav').getByRole('link', { name: 'My caseload', exact: true }).click()
    await expect(page).toHaveURL(/\/admin\/cm/)
    await expect(page.getByRole('heading', { name: /Good day/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'My caseload' })).toBeVisible()
    await expect(page.getByText('Scheduled CM supervision sessions')).toBeVisible()
  })

  test('supervision link navigates to CM meetings filter', async ({ page }) => {
    await loginCaseManager(page)
    await page.locator('.app-sidebar__nav').getByRole('link', { name: 'My caseload', exact: true }).click()
    await page.getByRole('link', { name: /CM meetings/i }).click()
    await expect(page).toHaveURL(/\/admin\/cm-meetings/)
  })
})
