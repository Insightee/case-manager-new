import assert from 'node:assert/strict'
import test from 'node:test'
import {
  isLikelyStaleAppError,
  isLikelyStaleLoginFailure,
} from './pwaStaleRecovery.js'

test('isLikelyStaleAppError matches chunk load messages', () => {
  assert.equal(isLikelyStaleAppError(new Error('Failed to fetch dynamically imported module')), true)
  assert.equal(isLikelyStaleAppError({ name: 'ChunkLoadError', message: 'x' }), true)
  assert.equal(isLikelyStaleAppError(new Error('Invalid credentials')), false)
  assert.equal(isLikelyStaleAppError(new Error('Load failed')), false)
})

test('isLikelyStaleLoginFailure ignores wrong password in standalone', () => {
  assert.equal(
    isLikelyStaleLoginFailure(new Error('Invalid credentials'), { standalone: true }),
    false,
  )
  assert.equal(
    isLikelyStaleLoginFailure(new Error('Failed to fetch'), { standalone: true }),
    false,
  )
  assert.equal(
    isLikelyStaleLoginFailure(new Error('Failed to fetch dynamically imported module'), {
      standalone: true,
    }),
    true,
  )
  assert.equal(isLikelyStaleLoginFailure(new Error('Failed to fetch'), { standalone: false }), false)
})
