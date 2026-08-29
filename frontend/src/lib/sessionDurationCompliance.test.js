import assert from 'node:assert/strict'
import test from 'node:test'
import {
  expectedDurationBounds,
  getDurationComplianceWarning,
  HOMECARE_MAX_MINS,
  HOMECARE_MIN_MINS,
  SHADOW_HALF_DAY_REFERENCE_MINS,
} from './sessionDurationCompliance.js'

test('expectedDurationBounds uses scheduled window', () => {
  const bounds = expectedDurationBounds({
    scheduled_date: '2026-08-05',
    start_time: '09:30:00',
    end_time: '11:00:00',
    product_module: 'homecare',
  })
  assert.equal(bounds.minMins, 90)
  assert.equal(bounds.maxMins, 90)
  assert.equal(bounds.hasSchedule, true)
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
