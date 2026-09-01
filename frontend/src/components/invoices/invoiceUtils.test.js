import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  STATEMENT_NOT_CONFIGURED,
  billingSummary,
  statementConfidence,
  statementLadder,
} from './invoiceUtils.js'

// Admin payloads carry client money and must keep showing it.
test('billingSummary shows client rate for admin per-session payload', () => {
  const out = billingSummary({
    billing_type: 'PER_SESSION',
    client_rate_per_session_inr: 1000,
    pay_share_amount_inr: 600,
  })
  assert.match(out, /₹1000\/session/)
  assert.match(out, /₹600 therapist pay/)
})

test('billingSummary shows client package amount for admin package payload', () => {
  const out = billingSummary({
    billing_type: 'PACKAGE',
    package_session_count: 20,
    package_amount_inr: 25000,
    compensation_mode: 'FIXED_LUMP',
    pay_share_amount_inr: 15000,
  })
  assert.match(out, /₹25000/)
  assert.match(out, /₹15000 therapist pay/)
})

// Therapist payloads are redacted at the API boundary: no client fields.
test('billingSummary hides client rate for redacted therapist per-session payload', () => {
  const out = billingSummary({
    billing_type: 'PER_SESSION',
    pay_share_amount_inr: 600,
  })
  assert.doesNotMatch(out, /\/session/)
  assert.doesNotMatch(out, /undefined/)
  assert.equal(out, '₹600 therapist pay')
})

test('billingSummary hides package price for redacted therapist package payload', () => {
  const out = billingSummary({
    billing_type: 'PACKAGE',
    package_session_count: 20,
    compensation_mode: 'FIXED_LUMP',
    pay_share_amount_inr: 15000,
  })
  assert.doesNotMatch(out, /25000/)
  assert.doesNotMatch(out, /undefined/)
  assert.equal(out, 'Package 20 sessions · ₹15000 therapist pay')
})

test('billingSummary fixed-lump package shows therapist fixed pay only', () => {
  const out = billingSummary({
    billing_type: 'PACKAGE',
    package_session_count: 20,
    compensation_mode: 'FIXED_LUMP',
    therapist_fixed_pay_inr: 25000,
  })
  assert.equal(out, 'Package 20 sessions · ₹25000 therapist pay')
})

test('billingSummary shows client monthly rate for admin monthly payload', () => {
  const out = billingSummary({
    billing_type: 'MONTHLY_FIXED',
    client_monthly_rate_inr: 29000,
    pay_share_amount_inr: 18000,
  })
  assert.match(out, /₹29000\/month/)
  assert.match(out, /₹18000 therapist pay/)
})

test('billingSummary handles unconfigured billing', () => {
  assert.equal(billingSummary(null), 'Billing not configured')
  assert.equal(billingSummary({}), 'Billing not configured')
})

// --- statement composition (T3) ---------------------------------------------

const STATEMENT = {
  month: '2026-07',
  month_label: 'July 2026',
  subtotal_inr: 18000,
  leave_deduction_inr: 1500,
  net_amount_inr: 16500,
  tds_rate_percent: 10,
  tds_inr: 1650,
  net_payable_inr: 14850,
  pending_late_count: 0,
  cases: [{ case_id: 1, therapist_share_inr: 18000 }],
}

test('statementLadder composes gross → leave → TDS → net from the engine payload', () => {
  const rows = statementLadder(STATEMENT)
  const byKey = Object.fromEntries(rows.map((r) => [r.key, r]))
  assert.equal(byKey.gross.amount, 18000)
  assert.equal(byKey.leave.amount, 1500)
  assert.equal(byKey.leave.kind, 'deduction')
  assert.equal(byKey.tds.amount, 1650)
  assert.equal(byKey.tds.kind, 'deduction')
  assert.equal(byKey.net.amount, 14850)
  assert.equal(byKey.net.kind, 'net')
})

test('statementLadder shows holdback / payment-date as placeholders; TDS when present', () => {
  const rows = statementLadder(STATEMENT)
  const tds = rows.find((r) => r.key === 'tds')
  assert.equal(tds.amount, 1650)
  assert.equal(tds.kind, 'deduction')
  for (const key of ['holdback', 'payment_date']) {
    const row = rows.find((r) => r.key === key)
    assert.ok(row, `${key} row present`)
    assert.equal(row.amount, null)
    assert.equal(row.note, STATEMENT_NOT_CONFIGURED)
  }
})

test('statementLadder falls back to TDS placeholder when rate not attached', () => {
  const rows = statementLadder({
    subtotal_inr: 10000,
    leave_deduction_inr: 0,
    net_amount_inr: 10000,
  })
  const tds = rows.find((r) => r.key === 'tds')
  assert.equal(tds.amount, null)
  assert.equal(tds.note, STATEMENT_NOT_CONFIGURED)
  assert.equal(rows.find((r) => r.key === 'net').amount, 10000)
})

test('statementLadder omits leave line when there is no deduction', () => {
  const rows = statementLadder({ ...STATEMENT, leave_deduction_inr: 0 })
  assert.equal(rows.find((r) => r.key === 'leave'), undefined)
})

test('statementLadder carries no client-price fields', () => {
  const serialized = JSON.stringify(statementLadder(STATEMENT))
  for (const leak of ['client_rate', 'package_amount', 'client_monthly', 'client_billing_mode']) {
    assert.doesNotMatch(serialized, new RegExp(leak))
  }
})

test('statementConfidence is provisional pre-cutover, never RECONCILED', () => {
  assert.equal(statementConfidence(STATEMENT, { cutover: false }), 'PARTIAL')
  assert.equal(statementConfidence({ ...STATEMENT, pending_late_count: 2 }, { cutover: false }), 'ESTIMATED')
  assert.notEqual(statementConfidence(STATEMENT, { cutover: true }), 'RECONCILED')
})
