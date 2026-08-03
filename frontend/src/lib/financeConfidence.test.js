import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  aggregateMoneyValues,
  confidenceTooltip,
  downgradeConfidence,
  formatInr,
  lowestConfidence,
  normalizeConfidence,
} from './financeConfidence.js'

describe('financeConfidence Stage 1', () => {
  it('13 never upgrades confidence', () => {
    assert.equal(downgradeConfidence('INCOMPLETE', 'PARTIAL'), 'INCOMPLETE')
    assert.equal(downgradeConfidence('ESTIMATED', 'RECONCILED'), 'ESTIMATED')
    assert.equal(downgradeConfidence('PARTIAL', 'ESTIMATED'), 'ESTIMATED')
  })

  it('11 normalize preserves RECONCILED (rank 0) and tooltips exist', () => {
    assert.equal(normalizeConfidence('RECONCILED'), 'RECONCILED')
    assert.equal(normalizeConfidence(null, { materialSourceMissing: true }), 'INCOMPLETE')
    assert.equal(normalizeConfidence(undefined), 'ESTIMATED')
    for (const level of ['RECONCILED', 'PARTIAL', 'ESTIMATED', 'INCOMPLETE']) {
      assert.ok(confidenceTooltip(level).length > 10)
    }
  })

  it('15–16 mixed totals use lowest confidence; missing amounts do not invent sum', () => {
    assert.equal(lowestConfidence(['PARTIAL', 'ESTIMATED', 'INCOMPLETE']), 'INCOMPLETE')
    assert.equal(lowestConfidence(['RECONCILED', 'PARTIAL']), 'PARTIAL')
    const incomplete = aggregateMoneyValues([
      { value: 100, confidence: 'PARTIAL', recordCount: 1 },
      { value: null, confidence: 'ESTIMATED', recordCount: 1 },
    ])
    assert.equal(incomplete.canSum, false)
    assert.equal(incomplete.value, null)
    assert.equal(incomplete.confidence, 'ESTIMATED')
    const ok = aggregateMoneyValues([
      { value: 100, confidence: 'PARTIAL', recordCount: 1 },
      { value: 50, confidence: 'ESTIMATED', recordCount: 2 },
    ])
    assert.equal(ok.canSum, true)
    assert.equal(ok.value, 150)
    assert.equal(ok.confidence, 'ESTIMATED')
  })

  it('10 formatInr returns null for missing amounts (do not invent ₹)', () => {
    assert.equal(formatInr(null), null)
    assert.equal(formatInr(undefined), null)
    assert.ok(formatInr(420000).includes('4'))
  })
})
