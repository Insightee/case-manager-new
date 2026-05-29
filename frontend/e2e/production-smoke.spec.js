/**
 * Production smoke — run against deployed Vercel + Railway (no local webServer).
 *
 *   cd frontend
 *   PLAYWRIGHT_SKIP_WEBSERVER=1 \
 *   PLAYWRIGHT_BASE_URL=https://frontend-omega-eight-92.vercel.app \
 *   PLAYWRIGHT_API_URL=https://case-manager-new-production.up.railway.app \
 *   npx playwright test e2e/production-smoke.spec.js
 */
import { test, expect } from '@playwright/test'
import { loginAdmin, loginTherapist, loginParent, portalNav, sidebarLink } from './helpers/auth.js'

const API = process.env.PLAYWRIGHT_API_URL || 'https://case-manager-new-production.up.railway.app'

test.describe('Production API', () => {
  test('health and auth login', async ({ request }) => {
    const health = await request.get(`${API}/health`)
    expect(health.ok()).toBeTruthy()
    const body = await health.json()
    expect(body.status).toBe('ok')
    expect(body.db_migration).toBeTruthy()
    if (body.smtp_configured !== undefined) {
      expect(body.smtp_configured).toBe(true)
    }

    const login = await request.post(`${API}/api/v1/auth/login`, {
      data: { email: 'superadmin@demo.com', password: 'demo123' },
    })
    expect(login.ok()).toBeTruthy()
    expect((await login.json()).access_token).toBeTruthy()
  })
})

test.describe('Production UI — admin', () => {
  test('admin core navigation', async ({ page }) => {
    await loginAdmin(page)
    await sidebarLink(page, 'Cases').click()
    await expect(page).toHaveURL(/\/admin\/cases/)

    await sidebarLink(page, 'Session Logs').click()
    await expect(page).toHaveURL(/\/admin\/logs/)

    await sidebarLink(page, 'Reports').click()
    await expect(page).toHaveURL(/\/admin\/reports/)

    await sidebarLink(page, 'IEP').click()
    await expect(page).toHaveURL(/\/admin\/iep/)

    const support = sidebarLink(page, 'Support & Incidents')
    if (await support.isVisible()) {
      await support.click()
      await expect(page).toHaveURL(/\/admin\/support/)
    }

    const people = portalNav(page).getByRole('link', { name: 'People', exact: true })
    if (await people.isVisible()) {
      await people.click()
      await expect(page).not.toHaveURL(/\/login/)
    }
  })

  test('admin billing or invoices area loads', async ({ page }) => {
    await loginAdmin(page)
    const billingLink = portalNav(page).getByRole('link', { name: 'Invoices & payments', exact: true })
    if (!(await billingLink.isVisible().catch(() => false))) {
      test.skip(true, 'Billing nav not visible for this admin role')
    }
    await billingLink.click()
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator('body')).not.toContainText('Failed to fetch')
  })
})

test.describe('Production UI — therapist', () => {
  test('therapist dashboard and logs', async ({ page }) => {
    await loginTherapist(page)
    await expect(page).toHaveURL(/\/therapist/)
    const logsLink = portalNav(page).getByRole('link', { name: /Session logs|Session Logs|Logs/i }).first()
    await logsLink.click()
    await expect(page).toHaveURL(/\/therapist\/logs/)
    await expect(page.locator('body')).not.toContainText('Network error')
  })
})

test.describe('Production UI — parent', () => {
  test('parent dashboard and reports', async ({ page }) => {
    await loginParent(page)
    await expect(page).toHaveURL(/\/parent/)
    await sidebarLink(page, 'Reports').click()
    await expect(page).toHaveURL(/\/parent\/reports/)
  })

  test('parent incidents or support when available', async ({ page }) => {
    await loginParent(page)
    await sidebarLink(page, 'Support & Incidents').click()
    await expect(page).not.toHaveURL(/\/login/)
  })
})
