import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  formatApiDateIN,
  formatDisplayDate,
  formatDisplayDateLabel,
  formatDisplayDateTime,
  formatDisplayDateTimeRange,
  formatDisplayDateRange,
  formatDateIN,
} from './datetime.js'

describe('datetime display (Indian DD-MM-YYYY)', () => {
  it('formatApiDateIN converts YYYY-MM-DD without timezone shift', () => {
    assert.equal(formatApiDateIN('2026-05-28'), '28-05-2026')
    assert.equal(formatApiDateIN('2026-05-28T00:00:00Z'), '28-05-2026')
    assert.equal(formatApiDateIN(null), null)
  })

  it('formatDisplayDate falls back to em dash', () => {
    assert.equal(formatDisplayDate('2026-01-02'), '02-01-2026')
    assert.equal(formatDisplayDate(''), '—')
  })

  it('formatDisplayDateTime and range include wall-clock times', () => {
    assert.equal(formatDisplayDateTime('2026-05-28', '14:30:00'), '28-05-2026 · 14:30')
    assert.equal(
      formatDisplayDateTimeRange('2026-05-28', '09:00', '10:30'),
      '28-05-2026 · 09:00–10:30',
    )
  })

  it('formatDisplayDateLabel prefixes weekday', () => {
    const label = formatDisplayDateLabel('2026-05-28')
    assert.match(label, /^Thu, 28-05-2026$/)
  })

  it('formatDisplayDateRange joins inclusive API dates', () => {
    assert.equal(formatDisplayDateRange('2026-05-01', '2026-05-31'), '01-05-2026 – 31-05-2026')
  })

  it('formatDateIN formats full ISO timestamps in IST', () => {
    const formatted = formatDateIN('2026-05-28T06:30:00Z')
    assert.equal(formatted, '28-05-2026')
  })
})
