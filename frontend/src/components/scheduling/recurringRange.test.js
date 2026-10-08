import assert from 'node:assert/strict'
import test from 'node:test'

import {
  addDaysIso,
  earlierWeekdayMessage,
  expandWeekdayDates,
  includeEarlierSelectedDays,
  nWeeksRange,
  weekdayKeyFromIso,
} from './recurringRange.js'

test('addDaysIso does not shift across a UTC boundary', () => {
  assert.equal(addDaysIso('2026-10-08', 0), '2026-10-08')
  assert.equal(addDaysIso('2026-10-08', 55), '2026-12-02')
})

test('weekdayKeyFromIso is Monday-first', () => {
  assert.equal(weekdayKeyFromIso('2026-10-08'), 'thu')
  assert.equal(weekdayKeyFromIso('2026-10-05'), 'mon')
})

test('eight week range includes Friday of the start week and not the prior Monday', () => {
  const range = nWeeksRange('2026-10-08', 8)
  assert.deepEqual(range, { from: '2026-10-08', to: '2026-12-02' })
  const days = expandWeekdayDates(['mon', 'wed', 'fri'], range.from, range.to)
  assert.equal(days[0], '2026-10-09')
  assert.equal(days.includes('2026-10-05'), false)
  assert.equal(days.includes('2026-10-07'), false)
  assert.equal(days.length, 24)
})

test('earlier weekdays can be pulled into the start week', () => {
  const message = earlierWeekdayMessage(['mon', 'wed', 'fri'], '2026-10-08')
  assert.match(message, /Monday/)
  assert.match(message, /Wednesday/)
  assert.equal(includeEarlierSelectedDays('2026-10-08', ['mon', 'wed', 'fri']), '2026-10-05')
})
