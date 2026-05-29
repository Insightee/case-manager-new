/**
 * Post-deploy verification: SMTP health, super-admin staff invite, client allotment.
 *
 *   cd frontend
 *   PLAYWRIGHT_SKIP_WEBSERVER=1 \
 *   PLAYWRIGHT_BASE_URL=https://frontend-omega-eight-92.vercel.app \
 *   PLAYWRIGHT_API_URL=https://case-manager-new-production.up.railway.app \
 *   npx playwright test e2e/production-deploy-verify.spec.js
 */
import { test, expect } from '@playwright/test'
import { loginAdmin } from './helpers/auth.js'

const API = process.env.PLAYWRIGHT_API_URL || 'https://case-manager-new-production.up.railway.app'
const BASE = process.env.PLAYWRIGHT_BASE_URL || 'https://frontend-omega-eight-92.vercel.app'
const SUPER_ADMIN_INVITE_EMAIL =
  process.env.PLAYWRIGHT_SUPER_ADMIN_EMAIL || 'nicky.lalu@gmail.com'

async function adminToken(request) {
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: 'superadmin@demo.com', password: 'demo123' },
  })
  expect(login.ok()).toBeTruthy()
  return (await login.json()).access_token
}

test.describe.configure({ mode: 'serial', timeout: 300_000 })

test.describe('Production deploy verify', () => {
  const ts = Date.now()
  const childLast = `Deploy${ts}`
  const parentEmail = `e2e.deploy.parent.${ts}@demo.com`

  test('API health and SMTP configured', async ({ request }) => {
    const health = await request.get(`${API}/health`)
    expect(health.ok()).toBeTruthy()
    const body = await health.json()
    expect(body.status).toBe('ok')
    if (body.smtp_configured === undefined) {
      test.skip(true, 'Deploy API with smtp_configured on /health not live yet')
    }
    expect(body.smtp_configured).toBe(true)
  })

  test('API — staff super-admin invite with email', async ({ request }) => {
    const token = await adminToken(request)
    const res = await request.post(`${API}/api/v1/admin/therapists/invite`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        email: SUPER_ADMIN_INVITE_EMAIL,
        full_name: 'Nicky Lalu',
        role_name: 'SUPER_ADMIN',
        send_email: true,
        module_assignments: [],
      },
    })
    if (res.status() === 400) {
      const detail = (await res.json()).detail || ''
      if (/already exists|pending invite/i.test(String(detail))) {
        const invites = await request.get(`${API}/api/v1/admin/invites`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const row = (await invites.json()).find((i) => i.email === SUPER_ADMIN_INVITE_EMAIL.toLowerCase())
        expect(row).toBeTruthy()
        const resend = await request.post(`${API}/api/v1/admin/invites/${row.id}/resend-email`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        expect(resend.ok(), await resend.text()).toBeTruthy()
        const body = await resend.json()
        expect(['queued', 'sent_sync']).toContain(body.email_delivery)
        return
      }
    }
    expect(res.ok(), await res.text()).toBeTruthy()
    const body = await res.json()
    expect(body.invite_url).toBeTruthy()
    expect(body.email_delivery).toBeTruthy()
    expect(['queued', 'sent_sync']).toContain(body.email_delivery)
  })

  test('UI — People staff super-admin invite flow', async ({ page }) => {
    await loginAdmin(page)
    await page.goto('/admin/people?tab=staff')
    await expect(page.getByRole('heading', { name: 'People', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Add staff user' })).toBeVisible()

    const staffPanel = page.locator('.admin-panel').filter({ hasText: 'Add staff user' })
    await staffPanel.locator('input[type="email"]').fill(SUPER_ADMIN_INVITE_EMAIL)
    await staffPanel.getByPlaceholder(/Shown on invite/i).or(staffPanel.locator('label').filter({ hasText: 'Full name' }).locator('input')).first().fill('Nicky Lalu')

    await staffPanel.getByRole('button', { name: 'Super Admin' }).click()
    await expect(staffPanel.getByRole('button', { name: 'Super Admin' })).toHaveClass(/is-active/)

    await staffPanel.getByRole('button', { name: 'Send invite' }).click()
    await expect(
      page.getByText(/Invite link generated|Check the inbox|queued|spam|SMTP is not configured/i).first(),
    ).toBeVisible({ timeout: 60_000 })

    const resend = page.getByRole('button', { name: 'Resend email' })
    if (await resend.first().isVisible().catch(() => false)) {
      await resend.first().click()
      await expect(page.getByText(/Check the inbox|queued|spam|Invite link/i).first()).toBeVisible({
        timeout: 30_000,
      })
    }
  })

  test('UI — create client via allotment wizard', async ({ page }) => {
    await loginAdmin(page)
    await page.goto('/admin/cases?allot=1')
    await expect(page.getByText(/Case allotment — step 1 of/i)).toBeVisible()

    await page.getByRole('radio', { name: 'New client' }).check()
    await page.getByRole('textbox', { name: 'Child first name' }).fill('Deploy')
    await page.getByRole('textbox', { name: 'Child last name' }).fill(childLast)
    await page.getByRole('textbox', { name: 'Parent name' }).fill(`Deploy Parent ${ts}`)
    await page.getByRole('textbox', { name: 'Parent email' }).fill(parentEmail)
    await page.getByRole('checkbox', { name: /Send portal invite email/i }).uncheck()

    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByText(/step 2 of/i)).toBeVisible()
    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByText(/step 3 of/i)).toBeVisible()

    const picker = page.locator('.admin-therapist-picker')
    const therapistSelect = picker.locator('select.admin-input')
    if (await therapistSelect.isVisible()) {
      await therapistSelect.selectOption({ index: 1 })
    } else {
      await picker.getByRole('button').first().click()
    }

    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByText(/step 4 of/i)).toBeVisible()
    await page.getByRole('button', { name: 'Save draft & continue' }).click()
    await expect(page.getByText(/step 5 of/i)).toBeVisible({ timeout: 90_000 })
    await expect(page.getByText(/Draft saved|draft/i).first()).toBeVisible({ timeout: 30_000 })
  })
})
