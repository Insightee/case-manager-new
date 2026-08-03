import assert from 'node:assert/strict'
import { test } from 'node:test'

import { billingSummary } from './invoiceUtils.js'

// Admin payloads carry client money and must keep showing it.
test('billingSummary shows client rate for admin per-session payload', () => {
  const out = billingSummary({
    billing_type: 'PER_SESSION',
    client_rate_per_session_inr: 1000,
    pay_share_amount_inr: 600,
  })
  assert.match(out, /₹1000\/session/)
  assert.match(out, /₹600 therapist share/)
})

test('billingSummary shows client package amount for admin package payload', () => {
  const out = billingSummary({
    billing_type: 'PACKAGE',
    package_session_count: 20,
    package_amount_inr: 25000,
    compensation_mode: 'PERCENTAGE',
    pay_share_amount_inr: 15000,
  })
  assert.match(out, /₹25000/)
  assert.match(out, /₹15000 therapist share/)
})

// Therapist payloads are redacted at the API boundary: no client fields.
test('billingSummary hides client rate for redacted therapist per-session payload', () => {
  const out = billingSummary({
    billing_type: 'PER_SESSION',
    pay_share_amount_inr: 600,
  })
  assert.doesNotMatch(out, /\/session/)
  assert.doesNotMatch(out, /undefined/)
  assert.equal(out, '₹600 therapist share')
})

test('billingSummary hides package price for redacted therapist package payload', () => {
  const out = billingSummary({
    billing_type: 'PACKAGE',
    package_session_count: 20,
    compensation_mode: 'PERCENTAGE',
    pay_share_amount_inr: 15000,
  })
  assert.doesNotMatch(out, /25000/)
  assert.doesNotMatch(out, /undefined/)
  assert.equal(out, 'Package 20 sessions · ₹15000 therapist share')
})

test('billingSummary fixed-lump package shows therapist fixed pay only', () => {
  const out = billingSummary({
    billing_type: 'PACKAGE',
    package_session_count: 20,
    compensation_mode: 'FIXED_LUMP',
    therapist_fixed_pay_inr: 25000,
  })
  assert.equal(out, 'Package 20 sessions · ₹25000 fixed pay')
})

test('billingSummary handles unconfigured billing', () => {
  assert.equal(billingSummary(null), 'Billing not configured')
  assert.equal(billingSummary({}), 'Billing not configured')
})
