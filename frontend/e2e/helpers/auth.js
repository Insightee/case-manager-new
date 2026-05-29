/** @param {import('@playwright/test').Page} page */
export function portalNav(page) {
  return page.getByRole('navigation', { name: 'Portal navigation' }).first()
}

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
  await portalNav(page).waitFor()
}

/** Sidebar nav link (avoids duplicate quick-action links). */
export function sidebarLink(page, label) {
  return portalNav(page).getByRole('link', { name: label, exact: true })
}

/** @param {import('@playwright/test').Page} page */
export async function loginParent(page) {
  await page.goto('/login')
  await page.getByRole('tab', { name: 'Client' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill('parent@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/parent/)
  await portalNav(page).waitFor()
}

/** @param {import('@playwright/test').Page} page */
export async function loginAdmin(page) {
  await page.goto('/login')
  await page.getByRole('tab', { name: 'Staff' }).click({ timeout: 90_000 })
  await page.getByRole('textbox', { name: 'Email' }).fill('superadmin@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/admin/)
  await portalNav(page).waitFor()
}

/** @param {import('@playwright/test').Page} page */
export async function loginCaseManager(page) {
  await page.goto('/login')
  await page.getByRole('tab', { name: 'Staff' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill('casemanager@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/admin/)
  await portalNav(page).waitFor()
}

/** @param {import('@playwright/test').Page} page */
export async function loginFinance(page) {
  await login(page, { email: 'finance@demo.com' })
  await page.waitForURL(/\/admin/)
  await portalNav(page).waitFor()
}
