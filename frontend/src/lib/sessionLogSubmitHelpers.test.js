import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  evaluateSessionLogSubmitReadiness,
  isSessionExpiredError,
  isSessionLateForSubmit,
  planSessionLogSubmitFailureActions,
  sessionLogSubmitFailureMessage,
  shouldQueueOfflineDraft,
} from './sessionLogSubmitHelpers.js'

describe('sessionLogSubmitHelpers late session (IST)', () => {
  it('is not late on the scheduled calendar day', () => {
    assert.equal(isSessionLateForSubmit({ scheduled_date: '2026-10-06' }, '2026-10-06'), false)
  })

  it('becomes late after midnight IST rolls the calendar day', () => {
    assert.equal(isSessionLateForSubmit({ scheduled_date: '2026-10-06' }, '2026-10-07'), true)
  })

  it('blocks submit at 00:01 IST when the form was opened the previous evening', () => {
    const readiness = evaluateSessionLogSubmitReadiness(
      { scheduled_date: '2026-10-06' },
      { activities_done: 'Sensory play and regulation', late_reason: '' },
      '2026-10-07',
    )
    assert.equal(readiness.ok, false)
    assert.equal(readiness.requireLateUi, true)
    assert.match(readiness.error, /previous day/i)
  })

  it('allows submit once late reason is filled after midnight', () => {
    const readiness = evaluateSessionLogSubmitReadiness(
      { scheduled_date: '2026-10-06' },
      { activities_done: 'Sensory play', late_reason: 'Submitted after travel' },
      '2026-10-07',
    )
    assert.equal(readiness.ok, true)
  })
})

describe('sessionLogSubmitHelpers submit failure plan', () => {
  it('does not queue offline sync for validation errors', () => {
    const plan = planSessionLogSubmitFailureActions(new Error('Late reason is required for sessions from past days'), {
      sessionId: 12,
      hasBody: true,
    })
    assert.equal(plan.queueOffline, false)
    assert.equal(plan.requireLateUi, true)
    assert.match(plan.errorMessage, /Late reason/i)
  })

  it('queues offline sync only for connection errors', () => {
    const err = new Error('You appear offline. Check your connection and try again.')
    err.isConnectionError = true
    const plan = planSessionLogSubmitFailureActions(err, { sessionId: 5, hasBody: true })
    assert.equal(plan.queueOffline, true)
    assert.equal(plan.draftSyncStatus, 'pending_sync')
  })

  it('saves local draft on session expiry without pending_sync', () => {
    const plan = planSessionLogSubmitFailureActions(new Error('Session expired. Please log in again.'), {
      sessionId: 9,
      hasBody: true,
    })
    assert.equal(plan.saveLocalDraft, true)
    assert.equal(plan.queueOffline, false)
    assert.match(plan.errorMessage, /sign in again/i)
  })

  it('shouldQueueOfflineDraft recognizes production timeout copy', () => {
    assert.equal(
      shouldQueueOfflineDraft(new Error('This is taking longer than expected (30s). Check your connection and try again.')),
      true,
    )
  })
})

it('403 permission denial is not treated as session expiry', () => {
  const err = Object.assign(new Error('Case access denied'), { status: 403 })
  assert.equal(isSessionExpiredError(err), false)
  assert.equal(sessionLogSubmitFailureMessage(err), 'Case access denied')
  const plan = planSessionLogSubmitFailureActions(err, { sessionId: 7, hasBody: true })
  assert.equal(plan.saveLocalDraft, false)
  assert.equal(plan.queueOffline, false)
})

it('401 is treated as session expiry', () => {
  const err = Object.assign(new Error('Not authenticated'), { status: 401 })
  assert.equal(isSessionExpiredError(err), true)
})
