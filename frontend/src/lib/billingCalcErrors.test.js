import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { test } from 'node:test'

import {
  MISSING_PACKAGE_COUNT_CODE,
  billingCalcErrorBannerText,
  parseBillingCalcApiError,
  resolveBillingCalcErrorMessage,
} from './billingCalcErrors.js'

const __dirname = dirname(fileURLToPath(import.meta.url))

test('parseBillingCalcApiError reads structured 422 detail from apiFetch errors', () => {
  const err = new Error('ignored')
  err.detail = {
    code: MISSING_PACKAGE_COUNT_CODE,
    message: 'Case PKG-1 is missing package session count.',
    caseId: 42,
    caseCode: 'PKG-1',
  }
  const parsed = parseBillingCalcApiError(err)
  assert.equal(parsed.code, MISSING_PACKAGE_COUNT_CODE)
  assert.match(parsed.message, /PKG-1/)
  assert.equal(parsed.caseId, 42)
})

test('therapist audience explains pause without exposing admin paths', () => {
  const text = billingCalcErrorBannerText(
    {
      code: MISSING_PACKAGE_COUNT_CODE,
      message: 'Case PKG-1 is missing package session count.',
      caseCode: 'PKG-1',
    },
    'therapist',
  )
  assert.match(text, /case manager/i)
  assert.match(text, /PKG-1/)
  assert.doesNotMatch(text, /data exceptions/i)
})

test('admin audience points to data exceptions and case fix', () => {
  const text = billingCalcErrorBannerText(
    {
      code: MISSING_PACKAGE_COUNT_CODE,
      message: 'Case PKG-1 is missing package session count.',
      caseCode: 'PKG-1',
    },
    'admin',
  )
  assert.match(text, /billing profile/i)
  assert.match(text, /Data exceptions/i)
})

test('parent audience does not surface therapist payout calc codes', () => {
  const text = billingCalcErrorBannerText(
    {
      code: MISSING_PACKAGE_COUNT_CODE,
      message: 'Case PKG-1 is missing package session count.',
    },
    'parent',
  )
  assert.match(text, /family statements/i)
  assert.doesNotMatch(text, /MISSING_PACKAGE/)
})

test('resolveBillingCalcErrorMessage falls back to err.message', () => {
  assert.equal(resolveBillingCalcErrorMessage(new Error('Network down')), 'Network down')
})

test('parent billing UI does not call therapist payout preview/submit APIs', () => {
  const parentBilling = readFileSync(
    join(__dirname, '../components/client-portal/ParentBillingPage.jsx'),
    'utf8',
  )
  assert.doesNotMatch(parentBilling, /\/api\/v1\/invoices\/preview/)
  assert.doesNotMatch(parentBilling, /\/api\/v1\/invoices\/submit/)
})

test('therapist invoice surfaces use BillingCalcErrorNotice for payout calc errors', () => {
  const files = [
    '../components/invoices/GenerateInvoiceModal.jsx',
    '../components/invoices/InvoicePreviewDrawer.jsx',
    '../components/invoices/InvoiceBreakdownModal.jsx',
  ]
  for (const rel of files) {
    const src = readFileSync(join(__dirname, rel), 'utf8')
    assert.match(src, /BillingCalcErrorNotice/, rel)
    assert.match(src, /audience="therapist"/, rel)
  }
})

test('admin raise payout panel uses BillingCalcErrorNotice for finance audience', () => {
  const src = readFileSync(
    join(__dirname, '../components/admin-portal/TherapistPayoutRaisePanel.jsx'),
    'utf8',
  )
  assert.match(src, /BillingCalcErrorNotice/)
  assert.match(src, /audience="admin"/)
})
