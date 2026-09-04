import assert from 'node:assert/strict'
import test from 'node:test'
import { getBlockingLogForCase, resolveBlockingLogSession } from './sessionStartRules.js'

const older = { id: 11, case_id: 7, child_name: 'Aarav', scheduled_date: '2026-08-30' }
const newer = { id: 22, case_id: 7, child_name: 'Aarav', scheduled_date: '2026-08-31' }
const other = { id: 33, case_id: 8, child_name: 'Mia', scheduled_date: '2026-08-29' }

test('getBlockingLogForCase returns the first needs-log visit for that case', () => {
  assert.equal(getBlockingLogForCase([older, newer, other], 7), older)
  assert.equal(getBlockingLogForCase([older, newer, other], 8), other)
  assert.equal(getBlockingLogForCase([older], 99), null)
})

test('resolveBlockingLogSession prefers the API blocking session id', () => {
  const resolved = resolveBlockingLogSession([older, newer, other], { blockingSessionId: 22 }, 7)
  assert.equal(resolved, newer)
})

test('resolveBlockingLogSession falls back to the case needs-log visit', () => {
  const resolved = resolveBlockingLogSession([older, newer, other], { message: 'Submit first' }, 7)
  assert.equal(resolved, older)
})
