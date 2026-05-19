import { chromium } from 'playwright'

const BASE = 'http://localhost:5173'
const PASS = 'demo123'

async function login(page, portalTab, email) {
  await page.goto(`${BASE}/login`)
  await page.getByRole('tab', { name: portalTab }).click()
  await page.getByRole('button', { name: email }).click()
  await page.getByRole('button', { name: /sign in/i }).click()
  await page.waitForURL(/\/(admin|therapist|parent|hr)/, { timeout: 20000 })
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage()
  const results = []

  try {
    await login(page, 'Admin', 'superadmin@demo.com')
    await page.goto(`${BASE}/admin/cases`)
    await page.waitForSelector('text=Cases', { timeout: 10000 })
    results.push(['admin cases page', true])

    const newCaseBtn = page.getByRole('button', { name: /new case/i })
    if (await newCaseBtn.isVisible()) {
      await newCaseBtn.click()
      await page.getByPlaceholder('IC-2026-099').fill('IC-UI-BILL-003')
      await page.locator('select').nth(0).selectOption({ index: 1 })
      await page.getByLabel(/service type/i).fill('UI smoke test')
      await page.getByRole('button', { name: /create case/i }).click()
      await page.waitForSelector('text=IC-UI-BILL-003', { timeout: 10000 })
      results.push(['admin create case', true])

      await page.getByRole('button', { name: /history/i }).first().click()
      await page.waitForSelector('text=Case billing', { timeout: 8000 })
      results.push(['admin billing panel', true])

      const therapistInput = page.getByPlaceholder('e.g. 3')
      if (await therapistInput.isVisible()) {
        await therapistInput.fill('4')
        await page.getByRole('button', { name: /assign/i }).click()
        await page.waitForTimeout(1500)
        results.push(['admin assign therapist', true])
      }
    }

    await page.goto(`${BASE}/admin/invoices`)
    await page.waitForSelector('text=Invoice review', { timeout: 10000 })
    results.push(['admin invoices page', true])

    await page.context().clearCookies()
    await page.evaluate(() => localStorage.clear())

    await login(page, 'Therapist', 'therapist@demo.com')
    await page.goto(`${BASE}/therapist/invoices`)
    await page.waitForSelector('text=Invoices', { timeout: 10000 })
    results.push(['therapist invoices page', true])

    await page.getByRole('button', { name: /generate invoice/i }).first().click()
    await page.waitForSelector('text=Generate invoice from logs', { timeout: 8000 })
    await page.waitForSelector('text=Validated sessions', { timeout: 15000 })
    await page.getByRole('button', { name: /review breakdown/i }).click()
    await page.waitForSelector('text=Invoice preview', { timeout: 10000 })
    results.push(['therapist invoice preview drawer', true])

    console.log(JSON.stringify({ ok: true, results }, null, 2))
  } catch (err) {
    await page.screenshot({ path: '/tmp/billing-smoke-fail.png', fullPage: true })
    console.log(JSON.stringify({ ok: false, error: String(err), results }, null, 2))
    process.exitCode = 1
  } finally {
    await browser.close()
  }
}

main()
