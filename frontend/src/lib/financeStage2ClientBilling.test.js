import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '../..')

function read(rel) {
  return readFileSync(join(root, rel), 'utf8')
}

describe('Stage 2 client billing static contracts', () => {
  it('removes agent debug probes from billing paths', () => {
    const files = [
      'src/lib/apiClient.js',
      'src/components/invoices/InvoicesPage.jsx',
      'src/components/admin-portal/AdminTherapistPayoutsPage.jsx',
      'src/components/admin-portal/AdminInvoicesPage.jsx',
    ]
    for (const f of files) {
      const text = read(f)
      assert.equal(text.includes('127.0.0.1:7284'), false, f)
      assert.equal(text.includes('#region agent log'), false, f)
    }
  })

  it('uses VITE_ENABLE_CLIENT_BILLING with legacy fallback', () => {
    const flags = read('src/lib/productFeatureFlags.js')
    assert.match(flags, /VITE_ENABLE_CLIENT_BILLING/)
    assert.match(flags, /isClientBillingVisible/)
    assert.match(flags, /VITE_ENABLE_BILLING/)
  })

  it('composer preview surfaces blocking exceptions and confidence badge', () => {
    const panel = read('src/components/admin-portal/InvoiceComposerPreviewPanel.jsx')
    assert.match(panel, /blockingExceptions/)
    assert.match(panel, /ConfidenceBadge/)
    assert.match(panel, /postableDraftCharges/)
    assert.match(panel, /Zoho sync/)
    assert.match(panel, /Not configured/)
    assert.match(panel, /Post charge/)
  })

  it('composer respects writesEnabled and canBuild guardrails', () => {
    const composer = read('src/components/admin-portal/InvoiceComposer.jsx')
    assert.match(composer, /useBillingRuntimeConfig/)
    assert.match(composer, /writesEnabled/)
    assert.match(composer, /canBuild/)
    assert.match(composer, /postDraftCharge/)
  })

  it('parent page preserves core behaviors and Forest Light classes', () => {
    const page = read('src/components/client-portal/ParentBillingPage.jsx')
    assert.match(page, /finance-stage2/)
    assert.match(page, /submitDispute/)
    assert.match(page, /submitPaymentClaim/)
    assert.match(page, /downloadPdf/)
    assert.match(page, /disputeLineIds/)
    assert.match(page, /parent-pay__mobile-card/)
    assert.match(page, /I paid offline/)
    assert.match(page, /Dispute invoice/)
    assert.equal(page.includes('127.0.0.1:7284'), false)
  })

  it('quality floor styles honor reduced motion and focus', () => {
    const css = read('src/styles/finance-stage2.css')
    assert.match(css, /prefers-reduced-motion/)
    assert.match(css, /:focus-visible/)
    assert.match(css, /--font-headline/)
    assert.match(css, /--font-mono/)
  })
})
