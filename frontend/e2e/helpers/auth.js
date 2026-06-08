/** @param {import('@playwright/test').Page} page */
export function portalNav(page) {
  return page.getByRole('navigation', { name: 'Portal navigation' }).first()
}

/** @param {import('@playwright/test').Page} page */
export async function login(page, { email, password = 'demo123', path = '/login' }) {
  await page.goto(path)
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
}

/** @param {import('@playwright/test').Page} page */
export async function loginTherapist(page) {
  await login(page, { email: 'therapist@demo.com', path: '/therapistlogin' })
  await page.waitForURL(/\/therapist/)
  const quickNav = page.getByRole('navigation', { name: 'Quick navigation' })
  if (await quickNav.isVisible()) {
    await quickNav.waitFor()
  } else {
    await portalNav(page).waitFor()
  }
}

/** Sidebar nav link (desktop). */
export function sidebarLink(page, label) {
  return portalNav(page).getByRole('link', { name: label, exact: true })
}

const THERAPIST_QUICK_NAV = {
  'Session Logs': 'Today',
  'My Cases': 'Cases',
  'Monthly Reports': 'Reports',
}

/** Mobile or desktop therapist nav — opens drawer when needed. */
export async function navigateTherapist(page, label) {
  const quickNav = page.getByRole('navigation', { name: 'Quick navigation' })
  if (await quickNav.isVisible()) {
    const quickLabel = THERAPIST_QUICK_NAV[label]
    if (quickLabel) {
      await quickNav.getByRole('link', { name: quickLabel, exact: true }).click()
      return
    }
    await page.getByRole('button', { name: 'Open navigation menu' }).click()
    await page.locator('#portal-nav-drawer').getByRole('link', { name: label, exact: true }).click()
    return
  }
  await sidebarLink(page, label).click()
}

/** @param {import('@playwright/test').Page} page */
export async function loginParent(page) {
  await page.goto('/clientlogin')
  await page.getByRole('textbox', { name: 'Email' }).fill('parent@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/parent/)
  await portalNav(page).waitFor()
}

/** @param {import('@playwright/test').Page} page */
export async function loginAdmin(page) {
  await page.goto('/stafflogin')
  await page.getByRole('textbox', { name: 'Email' }).fill('superadmin@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/admin/)
  await portalNav(page).waitFor()
}

/** @param {import('@playwright/test').Page} page */
export async function loginCaseManager(page) {
  await page.goto('/stafflogin')
  await page.getByRole('textbox', { name: 'Email' }).fill('casemanager@demo.com')
  await page.getByLabel('Password').fill('demo123')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(/\/admin/)
  await portalNav(page).waitFor()
}

/** @param {import('@playwright/test').Page} page */
export async function loginFinance(page) {
  await login(page, { email: 'finance@demo.com', path: '/stafflogin' })
  await page.waitForURL(/\/admin/)
  await portalNav(page).waitFor()
}
