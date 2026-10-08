import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  handoverBookingHintForTherapist,
  isSlotDateAllowedForTherapist,
  normalizeBookingErrorMessage,
  TRANSITION_BOOKING_ERROR,
} from './therapistTransitionBooking.js'

const policy = {
  outgoing_therapist_user_id: 10,
  incoming_therapist_user_id: 20,
  outgoing_may_book_through: '2026-08-12',
  incoming_may_book_from: '2026-08-10',
}

describe('therapistTransitionBooking', () => {
  it('allows outgoing through last handover day', () => {
    assert.equal(isSlotDateAllowedForTherapist(policy, 10, '2026-08-12'), true)
    assert.equal(isSlotDateAllowedForTherapist(policy, 10, '2026-08-13'), false)
  })

  it('allows incoming from first handover day', () => {
    assert.equal(isSlotDateAllowedForTherapist(policy, 20, '2026-08-09'), false)
    assert.equal(isSlotDateAllowedForTherapist(policy, 20, '2026-08-10'), true)
  })

  it('builds therapist-specific hints', () => {
    assert.match(handoverBookingHintForTherapist(policy, 10), /through 2026-08-12/)
    assert.match(handoverBookingHintForTherapist(policy, 20), /from 2026-08-10/)
  })

  it('normalizes server handover booking errors for all portals', () => {
    assert.equal(
      normalizeBookingErrorMessage('This booking is outside the handover window for this therapist.'),
      TRANSITION_BOOKING_ERROR,
    )
  })
})
