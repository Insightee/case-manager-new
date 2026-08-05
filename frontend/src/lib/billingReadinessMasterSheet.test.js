import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '../..')

function read(rel) {
  return readFileSync(join(root, rel), 'utf8')
}

describe('Billing readiness master sheet static contracts', () => {
  it('uses composer engine path and InsighteCase-only reconciliation copy', () => {
    const sheet = read('src/components/admin-portal/AdminBillingReadinessMasterSheet.jsx')
    assert.match(sheet, /billing-readiness-master-sheet/)
    assert.match(sheet, /no legacy payout invoices/)
    assert.match(sheet, /engineAmountInr/)
    assert.match(sheet, /brms-wide-wrap/)
  })

  it('wide view defines ~20 sticky columns with horizontal scroll container', () => {
    const sheet = read('src/components/admin-portal/AdminBillingReadinessMasterSheet.jsx')
    const css = read('src/styles/billing-readiness-master-sheet.css')
    const colMatches = sheet.match(/key:/g) || []
    assert.ok(colMatches.length >= 20, `expected >=20 wide columns, got ${colMatches.length}`)
    assert.match(css, /brms-wide-wrap/)
    assert.match(css, /min-width:\s*3200px/)
    assert.match(css, /position:\s*sticky/)
    assert.match(css, /brms-wide-table__sticky/)
  })

  it('finance layout uses single primary tab bar and full-width workspace classes', () => {
    const page = read('src/components/admin-portal/AdminInvoicesPage.jsx')
    const css = read('src/styles/billing-readiness-master-sheet.css')
    const shell = read('src/layouts/PortalShell.jsx')
    assert.match(page, /admin-page__tabs--single/)
    assert.doesNotMatch(page, /admin-page__subtabs/)
    assert.match(page, /admin-finance-inline-nav/)
    assert.match(css, /app-shell--finance-workspace/)
    assert.match(shell, /app-shell--sidebar-collapsed/)
  })
})
