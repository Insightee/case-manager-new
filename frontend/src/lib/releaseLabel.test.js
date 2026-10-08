import assert from 'node:assert/strict'
import test from 'node:test'

import {
  compareReleaseLabels,
  formatReleaseLabel,
  isDeployedReleaseNewer,
  istCalendarPartsFromDate,
  parseReleaseLabel,
} from './releaseLabel.js'

test('formatReleaseLabel builds iMMDD and optional same-day suffix', () => {
  assert.equal(formatReleaseLabel({ month: 10, day: 8 }), 'i1008')
  assert.equal(formatReleaseLabel({ month: 10, day: 8, releaseSeq: 1 }), 'i1008')
  assert.equal(formatReleaseLabel({ month: 10, day: 8, releaseSeq: 2 }), 'i1008.2')
  assert.equal(formatReleaseLabel({ month: 1, day: 3, releaseSeq: 4 }), 'i0103.4')
})

test('istCalendarPartsFromDate uses Asia/Kolkata near midnight boundary', () => {
  const beforeIstMidnight = new Date('2026-10-07T18:29:00.000Z')
  const afterIstMidnight = new Date('2026-10-07T18:30:00.000Z')
  const before = istCalendarPartsFromDate(beforeIstMidnight)
  const after = istCalendarPartsFromDate(afterIstMidnight)
  assert.equal(before.month, 10)
  assert.equal(before.day, 7)
  assert.equal(after.month, 10)
  assert.equal(after.day, 8)
  assert.equal(formatReleaseLabel(before), 'i1007')
  assert.equal(formatReleaseLabel(after), 'i1008')
})

test('parseReleaseLabel and compareReleaseLabels order releases', () => {
  assert.deepEqual(parseReleaseLabel('i1008'), { mmdd: 1008, seq: 1 })
  assert.deepEqual(parseReleaseLabel('i1008.3'), { mmdd: 1008, seq: 3 })
  assert.equal(compareReleaseLabels('i1006', 'i1008'), -1)
  assert.equal(compareReleaseLabels('i1008.2', 'i1008.3'), -1)
  assert.equal(compareReleaseLabels('i1008', 'i1008'), 0)
})

test('isDeployedReleaseNewer uses release labels only', () => {
  assert.equal(isDeployedReleaseNewer('i1006', 'i1008'), true)
  assert.equal(isDeployedReleaseNewer('i1008', 'i1008'), false)
  assert.equal(isDeployedReleaseNewer('i1008.2', 'i1008.3'), true)
  assert.equal(isDeployedReleaseNewer('dev', 'i1008'), false)
})
