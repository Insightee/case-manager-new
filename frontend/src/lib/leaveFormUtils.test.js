import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { formatLeaveDayAllocations, formatLeaveRecordSplit, formatLeaveSplitLabel } from './leaveFormUtils.js'

describe('leave day split labels', () => {
  it('lists each date with paid or unpaid status', () => {
    assert.equal(
      formatLeaveDayAllocations([
        { date: '2026-08-31', status: 'paid' },
        { date: '2026-09-01', status: 'unpaid' },
      ]),
      '31-08-2026 paid · 01-09-2026 unpaid',
    )
  })

  it('prefers day allocations on a saved leave row', () => {
    assert.equal(
      formatLeaveRecordSplit({
        paid_days: 1,
        unpaid_days: 1,
        day_allocations: [
          { date: '2026-08-31', status: 'paid' },
          { date: '2026-09-01', status: 'unpaid' },
        ],
      }),
      '31-08-2026 paid · 01-09-2026 unpaid',
    )
  })

  it('uses the suggest message when present', () => {
    assert.equal(
      formatLeaveSplitLabel({
        message: '31 Aug paid. 01 Sep unpaid — you will not be paid for the unpaid day.',
        paid_days: 1,
        unpaid_days: 1,
      }),
      '31 Aug paid. 01 Sep unpaid — you will not be paid for the unpaid day.',
    )
  })
})
