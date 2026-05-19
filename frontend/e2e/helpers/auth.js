/** @param {import('@playwright/test').Page} page */
export async function login(page, { email, password = 'demo123' }) {
  await page.goto('/login')
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
}

/** @param {import('@playwright/test').Page} page */
export async function loginTherapist(page) {
  await login(page, { email: 'therapist@demo.com' })
  await page.waitForURL(/\/therapist/)
  await page.locator('.app-sidebar__nav').waitFor()
}

/** Sidebar nav link (avoids duplicate quick-action links). */
export function sidebarLink(page, label) {
  return page.locator('.app-sidebar__nav').getByRole('link', { name: label, exact: true })
}

/** @param {import('@playwright/test').Page} page */
export async function loginParent(page) {
  await page.goto('/login')
  await page.getByRole('tab', { name: 'Client' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill('parent@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/parent/)
  await page.locator('.app-sidebar__nav').waitFor()
}

/** @param {import('@playwright/test').Page} page */
export async function loginAdmin(page) {
  await page.goto('/login')
  await page.getByRole('tab', { name: 'Admin' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill('superadmin@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/admin/)
}
