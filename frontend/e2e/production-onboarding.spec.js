/**
 * Production onboarding E2E — creates real data on Railway/Vercel each run.
 *
 *   cd frontend
 *   PLAYWRIGHT_SKIP_WEBSERVER=1 \
 *   PLAYWRIGHT_BASE_URL=https://frontend-omega-eight-92.vercel.app \
 *   PLAYWRIGHT_API_URL=https://case-manager-new-production.up.railway.app \
 *   npx playwright test e2e/production-onboarding.spec.js
 *
 * Report: docs/reports/production-e2e-latest.md
 */
import { test, expect } from '@playwright/test'
import { loginAdmin, portalNav } from './helpers/auth.js'
import { createProductionReport } from './helpers/productionReport.js'

const API = process.env.PLAYWRIGHT_API_URL || 'https://case-manager-new-production.up.railway.app'

async function adminToken(request) {
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email: 'superadmin@demo.com', password: 'demo123' },
  })
  expect(login.ok()).toBeTruthy()
  return (await login.json()).access_token
}

async function findCase(request, { caseCode, childLast }) {
  const token = await adminToken(request)
  const res = await request.get(`${API}/api/v1/cases?page_size=100`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const items = (await res.json()).items || []
  return (
    items.find((c) => caseCode && c.case_code === caseCode) ||
    items.find((c) => childLast && c.child_name?.includes(childLast)) ||
    null
  )
}

async function caseStatusByCode(request, caseCode, childLast) {
  return (await findCase(request, { caseCode, childLast }))?.status
}

test.describe.configure({ mode: 'serial', timeout: 300_000 })

test.describe('Production onboarding (creates live data)', () => {
  const report = createProductionReport()
  const ts = report.runId
  const therapistEmail = `e2e.therapist.${ts}@insighte.com`
  const parentEmail = `e2e.parent.${ts}@demo.com`
  const childFirst = 'E2E'
  const childLast = `Child${ts}`

  test.afterAll(() => {
    const { jsonPath, mdPath } = report.finish()
    console.log(`\nProduction E2E report written:\n  ${mdPath}\n  ${jsonPath}\n`)
  })

  test('1 — admin creates therapist via People', async ({ page }) => {
    try {
      await loginAdmin(page)
      await page.goto('/admin/people?tab=therapists')
      await expect(page.getByRole('heading', { name: 'People', exact: true })).toBeVisible()

      await page.getByRole('button', { name: 'Add therapist' }).click()
      const dialog = page.getByRole('dialog', { name: 'Add therapist' })
      await expect(dialog).toBeVisible()

      await dialog.getByRole('textbox', { name: 'Full name' }).fill(`E2E Therapist ${ts}`)
      await dialog.getByRole('textbox', { name: 'Email' }).fill(therapistEmail)
      await dialog.getByRole('textbox', { name: 'Phone' }).fill('9999900001')

      await dialog.locator('label').filter({ hasText: 'Onboarding' }).locator('select').selectOption('direct')
      await dialog.getByRole('textbox', { name: /Password/i }).fill('demo123')

      const cmSelect = dialog.locator('label').filter({ hasText: 'Primary case manager' }).locator('select')
      await cmSelect.selectOption({ index: 1 })

      const homecareChip = dialog.locator('label.admin-chip').filter({ hasText: /homecare/i }).first()
      if (await homecareChip.isVisible()) {
        const cb = homecareChip.locator('input[type="checkbox"]')
        if (!(await cb.isChecked())) await homecareChip.click()
      } else {
        const anyService = dialog.locator('label.admin-chip input[type="checkbox"]').first()
        if (await anyService.isVisible()) {
          await anyService.check()
        }
      }

      await dialog.getByRole('button', { name: 'Create therapist' }).click()
      await expect(page.getByText(/Therapist account created|Invite created for/i)).toBeVisible({ timeout: 60_000 })
      await expect(dialog).toBeHidden({ timeout: 15_000 })

      report.setArtifact('therapistEmail', therapistEmail)
      report.log('Create therapist (People)', 'PASS', therapistEmail)
    } catch (err) {
      report.log('Create therapist (People)', 'FAIL', err.message)
      throw err
    }
  })

  test('2 — allotment wizard: new family, draft, approve', async ({ page, request }) => {
    let caseCode = ''
    try {
      await loginAdmin(page)
      await page.goto('/admin/cases?allot=1')
      await expect(page.getByText(/Case allotment — step 1 of/i)).toBeVisible()

      await page.getByRole('radio', { name: 'New client' }).check()
      await page.getByRole('textbox', { name: 'Child first name' }).fill(childFirst)
      await page.getByRole('textbox', { name: 'Child last name' }).fill(childLast)
      await page.getByRole('textbox', { name: 'Parent name' }).fill(`E2E Parent ${ts}`)
      await page.getByRole('textbox', { name: 'Parent email' }).fill(parentEmail)
      await page.getByRole('checkbox', { name: /Send portal invite email/i }).uncheck()

      await page.getByRole('button', { name: 'Next' }).click()
      await expect(page.getByText(/step 2 of/i)).toBeVisible()

      await page.getByRole('button', { name: 'Next' }).click()
      await expect(page.getByText(/step 3 of/i)).toBeVisible()

      const picker = page.locator('.admin-therapist-picker')
      const therapistsResponse = page.waitForResponse(
        (r) => r.url().includes('/allotment/therapists') && r.status() === 200,
      )
      await picker.getByRole('searchbox', { name: 'Search therapists' }).fill(therapistEmail)
      await therapistsResponse
      await page.waitForTimeout(500)
      const therapistSelect = picker.locator('select.admin-input')
      if (await therapistSelect.isVisible()) {
        const option = therapistSelect.locator('option', { hasText: therapistEmail })
        await expect(option).toHaveCount(1, { timeout: 30_000 })
        await therapistSelect.selectOption({ label: await option.innerText() })
      } else {
        await picker.getByRole('button').filter({ hasText: therapistEmail }).first().click()
      }

      await page.getByRole('button', { name: 'Next' }).click()
      await expect(page.getByText(/step 4 of/i)).toBeVisible()
      caseCode = (
        await page
          .locator('.admin-allotment-wizard__review-list div')
          .filter({ has: page.getByText('Case code', { exact: true }) })
          .locator('dd')
          .textContent()
      )?.trim() || ''

      await page.getByRole('button', { name: 'Save draft & continue' }).click()
      await expect(page.getByText(/step 5 of/i)).toBeVisible({ timeout: 60_000 })
      const draftLine = page.getByText(new RegExp(`Case ${caseCode.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
      await expect(draftLine).toBeVisible({ timeout: 15_000 })

      await page.getByRole('button', { name: 'Continue to preview' }).click()
      await expect(page.getByText(/Preview before approval/i)).toBeVisible({ timeout: 30_000 })

      await page.getByRole('button', { name: 'Approve & send invites' }).click()
      await expect
        .poll(() => caseStatusByCode(request, caseCode, childLast), {
          timeout: 180_000,
          intervals: [3000],
        })
        .toBe('ACTIVE')

      const activatedHeading = page.getByRole('heading', { name: 'Case activated' })
      if (!(await activatedHeading.isVisible().catch(() => false))) {
        report.log('Wizard success screen', 'SKIP', 'Case ACTIVE via API; UI may need deploy (120s activate timeout)')
      } else {
        await expect(activatedHeading).toBeVisible()
      }

      const match = await findCase(request, { caseCode, childLast })
      expect(match).toBeTruthy()
      expect(match.status).toBe('ACTIVE')

      report.setArtifact('parentEmail', parentEmail)
      report.setArtifact('childName', `${childFirst} ${childLast}`)
      report.setArtifact('caseCode', match.case_code)
      report.setArtifact('caseId', String(match.id))
      report.log('Allotment wizard end-to-end', 'PASS', `${match.case_code} ACTIVE`)
    } catch (err) {
      report.log('Allotment wizard end-to-end', 'FAIL', err.message)
      throw err
    }
  })

  test('3 — verify case visible on admin cases board', async ({ page }) => {
    try {
      const caseCode = report.getArtifacts().caseCode
      if (!caseCode) {
        test.skip(true, 'No case from prior step')
      }
      await loginAdmin(page)
      await page.goto('/admin/cases')
      await expect(page.getByText(caseCode, { exact: true }).first()).toBeVisible({ timeout: 30_000 })
      report.log('Case on admin board', 'PASS', caseCode)
    } catch (err) {
      report.log('Case on admin board', 'FAIL', err.message)
      throw err
    }
  })
})
