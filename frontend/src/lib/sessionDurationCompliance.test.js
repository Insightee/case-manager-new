import assert from 'node:assert/strict'
import test from 'node:test'
import {
  expectedDurationBounds,
  getDurationComplianceWarning,
  HOMECARE_MAX_MINS,
  HOMECARE_MIN_MINS,
  SCHEDULED_DURATION_TOLERANCE_MINS,
  SHADOW_HALF_DAY_REFERENCE_MINS,
} from './sessionDurationCompliance.js'

test('expectedDurationBounds uses scheduled window', () => {
  const bounds = expectedDurationBounds({
    scheduled_date: '2026-08-05',
    start_time: '09:30:00',
    end_time: '11:00:00',
    product_module: 'homecare',
  })
  assert.equal(bounds.minMins, 75)
  assert.equal(bounds.maxMins, 105)
  assert.equal(bounds.referenceLabel, 'scheduled 90 min')
  assert.equal(bounds.hasSchedule, true)
  assert.equal(SCHEDULED_DURATION_TOLERANCE_MINS, 15)
})

test('expectedDurationBounds shadow half day', () => {
  const bounds = expectedDurationBounds({
    product_module: 'shadow_support',
    day_type: 'HALF_DAY',
  })
  assert.equal(bounds.minMins, SHADOW_HALF_DAY_REFERENCE_MINS)
})

test('getDurationComplianceWarning flags short homecare visit', () => {
  const warning = getDurationComplianceWarning({
    session: {
      status: 'COMPLETED',
      product_module: 'homecare',
      actual_start_at: '2026-08-05T04:00:00Z',
      actual_end_at: '2026-08-05T04:45:00Z',
    },
    attendanceStatus: 'PRESENT',
  })
  assert.ok(warning)
  assert.equal(warning.code, 'under_minimum')
  assert.equal(warning.actualMins, 45)
  assert.equal(warning.message, '45 min — below homecare (1–4 hours).')
})

test('getDurationComplianceWarning skips absence logs', () => {
  const warning = getDurationComplianceWarning({
    session: { status: 'COMPLETED', product_module: 'homecare' },
    attendanceStatus: 'CLIENT_ABSENT',
  })
  assert.equal(warning, null)
})

test('getDurationComplianceWarning none when in homecare range', () => {
  const warning = getDurationComplianceWarning({
    session: {
      status: 'COMPLETED',
      product_module: 'homecare',
      actual_start_at: '2026-08-05T04:00:00Z',
      actual_end_at: '2026-08-05T05:30:00Z',
    },
    attendanceStatus: 'PRESENT',
  })
  assert.equal(warning, null)
  assert.equal(HOMECARE_MIN_MINS, 60)
  assert.equal(HOMECARE_MAX_MINS, 240)
})

function scheduledSession(durationMins) {
  const start = Date.parse('2026-08-05T04:00:00Z')
  const end = new Date(start + durationMins * 60_000).toISOString()
  return {
    status: 'COMPLETED',
    product_module: 'homecare',
    scheduled_date: '2026-08-05',
    start_time: '09:30:00',
    end_time: '11:00:00',
    actual_start_at: '2026-08-05T04:00:00Z',
    actual_end_at: end,
  }
}

test('getDurationComplianceWarning none within scheduled ±15 min', () => {
  assert.equal(
    getDurationComplianceWarning({ session: scheduledSession(80), attendanceStatus: 'PRESENT' }),
    null,
  )
  assert.equal(
    getDurationComplianceWarning({ session: scheduledSession(100), attendanceStatus: 'PRESENT' }),
    null,
  )
})

test('getDurationComplianceWarning flags outside scheduled ±15 min', () => {
  const under = getDurationComplianceWarning({
    session: scheduledSession(70),
    attendanceStatus: 'PRESENT',
  })
  assert.ok(under)
  assert.equal(under.code, 'under_minimum')
  assert.equal(under.message, '70 min vs scheduled 90 min (±15).')
  const over = getDurationComplianceWarning({
    session: scheduledSession(110),
    attendanceStatus: 'PRESENT',
  })
  assert.ok(over)
  assert.equal(over.code, 'over_maximum')
  assert.equal(over.message, '110 min vs scheduled 90 min (±15).')
})
