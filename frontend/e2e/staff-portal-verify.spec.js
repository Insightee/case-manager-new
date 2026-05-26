import { test, expect } from '@playwright/test'

async function loginStaff(page, email) {
  await page.goto('/login')
  await page.getByRole('tab', { name: 'Staff' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/admin/)
}

test.describe('Staff portal regression', () => {
  test('CM cases filter defaults to self; HR and Finance land correctly', async ({ page }) => {
    await loginStaff(page, 'casemanager@demo.com')
    await page.goto('/admin/cases')
    await page.getByLabel('Case manager').waitFor()
    const cmValue = await page.getByLabel('Case manager').inputValue()
    expect(cmValue).not.toBe('all')
    expect(cmValue).not.toBe('')

    await page.goto('/login')
    await loginStaff(page, 'hr@demo.com')
    await expect(page).toHaveURL(/\/admin\/people/)

    await page.goto('/login')
    await loginStaff(page, 'finance@demo.com')
    await expect(page).toHaveURL(/\/admin\/invoices/)
    await expect(
      page.locator('.app-sidebar__nav').getByRole('link', { name: 'Invoices & payments' }),
    ).toHaveClass(/is-active/)
  })
})
