/**
 * End-to-end billing demo: therapist payout → parent payment/dispute → finance review.
 * Runs against seeded demo accounts with billing flags enabled (see playwright.config.js).
 */
import { test, expect } from '@playwright/test'
import { loginAdmin, loginFinance, loginParent, loginTherapist } from './helpers/auth.js'

const THERAPIST_INVOICE_MONTH = 'May 2026'
const CLIENT_INVOICE_NUMBER = 'INV-2026-0201'

async function resetSession(context, page) {
  await context.clearCookies()
  await page.evaluate(() => localStorage.clear())
}

async function openParentInvoice(page, invoiceNumber) {
  const dismissInstall = page.getByRole('button', { name: /dismiss install suggestion/i })
  if (await dismissInstall.isVisible().catch(() => false)) {
    await dismissInstall.click()
  }

  const mobileBtn = page.locator('.parent-pay__mobile-list').getByRole('button').filter({ hasText: invoiceNumber })
  if ((await mobileBtn.count()) > 0 && (await mobileBtn.first().isVisible())) {
    await mobileBtn.first().click()
    return
  }

  await page
    .getByRole('row')
    .filter({ hasText: invoiceNumber })
    .getByRole('button', { name: /^view$/i })
    .click()
}

async function openAdminInvoice(page, invoiceNumber) {
  const viewBtn = page
    .getByRole('row')
    .filter({ hasText: invoiceNumber })
    .getByRole('button', { name: /^view$/i })
  if (await viewBtn.count()) {
    await viewBtn.click()
    return
  }
  await page.getByRole('button', { name: /^view$/i }).first().click()
}

async function resolveClientDispute(page, invoiceNumber, note) {
  const mobileCard = page.getByRole('article').filter({ hasText: invoiceNumber })
  if (await mobileCard.first().isVisible().catch(() => false)) {
    const card = mobileCard.first()
    const moreDetails = card.getByText('More details')
    if (await moreDetails.isVisible({ timeout: 2000 }).catch(() => false)) {
      await moreDetails.click()
    }
    const reviewBtn = card.getByRole('button', { name: /review dispute|^review$/i })
    if (await reviewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await reviewBtn.click()
    }
    await card.locator('textarea').first().fill(note)
    await card.getByRole('button', { name: /^resolve$/i }).click()
    return
  }

  await page.getByRole('button', { name: /^review$/i }).first().click()
  await page.getByPlaceholder(/resolution note/i).fill(note)
  await page.getByRole('button', { name: /^resolve$/i }).first().click()
}

test.describe('Billing full flow', () => {
  test.setTimeout(180_000)

  test('therapist → admin → parent → finance money-in and money-out', async ({ page, context }) => {
    // ── THERAPIST: preview May invoice, add forgotten session, submit ──
    await loginTherapist(page)
    await page.goto('/therapist/invoices')
    await expect(page.getByRole('heading', { name: 'Invoices', exact: true })).toBeVisible()

    await page.getByRole('button', { name: /generate invoice/i }).first().click()
    await expect(page.getByRole('heading', { name: /generate invoice from logs/i })).toBeVisible()

    await page.locator('#inv-month').selectOption({ label: THERAPIST_INVOICE_MONTH })
    await expect(page.getByText(/validated sessions/i).first()).toBeVisible({ timeout: 20_000 })

    await page.getByRole('button', { name: /review breakdown/i }).click()
    await expect(page.getByRole('heading', { name: /invoice preview/i })).toBeVisible()

    await page.getByRole('button', { name: /add forgotten session/i }).first().click()
    await page.getByLabel('Session date').fill('2026-05-20')
    await page.getByPlaceholder(/logged after clinic visit/i).fill('E2E demo: forgot to log after home visit')
    await page.getByRole('button', { name: /^add session$/i }).click()
    await expect(page.getByText(/pending approval|excluded from payout/i).first()).toBeVisible({ timeout: 15_000 })

    await page.getByRole('button', { name: /submit for review/i }).click()
    await expect(page.getByText(/submitted/i).first()).toBeVisible({ timeout: 15_000 })

    // ── ADMIN: approve pending session logs (including late-added May session) ──
    await resetSession(context, page)
    await loginAdmin(page)
    await page.goto('/admin/cm/logs')
    await expect(page.getByRole('heading', { name: /session log review/i })).toBeVisible({ timeout: 15_000 })

    for (let i = 0; i < 6; i += 1) {
      const approveLogBtn = page.getByRole('button', { name: /^approve$/i }).first()
      if (!(await approveLogBtn.isVisible({ timeout: 2000 }).catch(() => false))) break
      await approveLogBtn.click()
      await page.waitForTimeout(600)
    }
    await expect(page.getByText(/no pending logs|you're all caught up/i).first()).toBeVisible({ timeout: 15_000 })

    // ── FINANCE: approve therapist May invoice ──
    await resetSession(context, page)
    await loginFinance(page)
    await page.goto('/admin/therapist-payouts?sub=payouts&view=list&status=IN_REVIEW')
    await expect(page.getByText(/therapist invoices in review/i)).toBeVisible({ timeout: 15_000 })

    const mayRow = page.getByRole('row').filter({ hasText: THERAPIST_INVOICE_MONTH })
    if (await mayRow.count()) {
      await mayRow.getByRole('button', { name: 'Approve' }).click()
    } else {
      await page.getByRole('button', { name: 'Approve' }).first().click()
    }
    await expect(page.getByText(/payout approved|approved/i).first()).toBeVisible({ timeout: 15_000 })

    // ── PARENT: dispute invoice + submit offline payment claim ──
    await resetSession(context, page)
    await loginParent(page)
    await page.goto('/parent/billing')
    await expect(page.getByRole('heading', { name: /your statements/i })).toBeVisible({ timeout: 15_000 })

    await openParentInvoice(page, CLIENT_INVOICE_NUMBER)
    await expect(page.getByRole('dialog', { name: /invoice detail/i })).toBeVisible()

    await page.getByRole('button', { name: /dispute invoice/i }).click()
    await page.getByLabel(/dispute details/i).fill('E2E demo: session amount looks incorrect for May visit.')
    await page.getByRole('button', { name: /submit dispute/i }).click()
    await expect(page.getByText(/dispute submitted/i).first()).toBeVisible({ timeout: 10_000 })

    await page.getByRole('button', { name: /i paid offline/i }).click()
    await page.getByLabel(/amount \(inr\)/i).fill('2000')
    await page.getByLabel(/reference \(optional\)/i).fill('E2E-UPI-8839201')
    await page.getByRole('button', { name: /submit for review/i }).click()
    await expect(page.getByText(/submitted for review|payment submitted/i).first()).toBeVisible({ timeout: 15_000 })

    // ── FINANCE: resolve dispute + confirm payment claim ──
    await resetSession(context, page)
    await loginFinance(page)

    await page.goto('/admin/invoices?tab=disputes')
    await expect(page.getByRole('heading', { name: /billing disputes/i })).toBeVisible({ timeout: 15_000 })
    await resolveClientDispute(page, CLIENT_INVOICE_NUMBER, 'E2E resolved — line verified with therapist log.')
    await expect(page.getByText(/no open disputes|resolved/i).first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/admin/invoices?tab=payments&claims=pending')
    await expect(page.getByText('Claims pending review')).toBeVisible({ timeout: 15_000 })

    await openAdminInvoice(page, CLIENT_INVOICE_NUMBER)
    await page.getByRole('button', { name: /payments & disputes/i }).click()
    await page.getByRole('button', { name: /confirm payment|^confirm$/i }).first().click()
    await expect(page.getByText(/confirmed|already confirmed/i).first()).toBeVisible({ timeout: 15_000 })

    // ── PARENT: download receipt after finance confirmation ──
    await resetSession(context, page)
    await loginParent(page)
    await page.goto('/parent/billing')
    await page.waitForLoadState('networkidle')

    if (test.info().project.name === 'mobile-chrome') {
      await page
        .locator('.parent-pay__mobile-list button')
        .filter({ hasText: CLIENT_INVOICE_NUMBER })
        .click({ force: true, timeout: 15_000 })
    } else {
      await openParentInvoice(page, CLIENT_INVOICE_NUMBER)
    }

    const receiptBtn = page.getByRole('button', { name: /download receipt/i }).first()
    await expect(receiptBtn).toBeVisible({ timeout: 15_000 })
    const downloadPromise = page.waitForEvent('download')
    await receiptBtn.click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/receipt/i)

    // ── FINANCE: payout queue + Monday briefing ──
    await resetSession(context, page)
    await loginFinance(page)

    await page.goto('/admin/therapist-payouts?sub=payouts&view=queue')
    await expect(page.getByText(/payout finance queue|money out|payable now/i).first()).toBeVisible({ timeout: 15_000 })

    await page.goto('/admin/invoices?tab=overview')
    await expect(page.getByText(/monday briefing|finance snapshot/i).first()).toBeVisible({ timeout: 15_000 })
  })
})
