/** Shared copy and helpers for therapist handover booking windows (all portals). */

export const TRANSITION_BOOKING_ERROR =
  'This booking is outside the handover window for this therapist. Outgoing therapists can book through the last handover day; incoming therapists can book from the first handover day onward.'

export const TRANSITION_HANDOVER_BANNER =
  'Therapist handover in progress. Both therapists can keep sessions, logs, and clinical work within each therapist’s handover dates. Billing, reassignment, and structural case edits stay paused until the handover completes.'

export const TRANSITION_PARENT_BOOKING_HINT =
  'During a therapist handover, you can only book with each therapist on dates allowed for that therapist’s role (outgoing through the last handover day; incoming from the first handover day).'

export function handoverPolicyFromTherapists(therapists) {
  if (!Array.isArray(therapists) || !therapists.length) return null
  return therapists.find((t) => t.handover_booking_policy)?.handover_booking_policy || null
}

export function isSlotDateAllowedForTherapist(policy, therapistUserId, isoDate) {
  if (!policy || !isoDate) return true
  const tid = Number(therapistUserId)
  const day = String(isoDate).slice(0, 10)
  if (tid === Number(policy.outgoing_therapist_user_id)) {
    return day <= policy.outgoing_may_book_through
  }
  if (tid === Number(policy.incoming_therapist_user_id)) {
    return day >= policy.incoming_may_book_from
  }
  return false
}

export function handoverBookingHintForTherapist(policy, therapistUserId) {
  if (!policy) return null
  const tid = Number(therapistUserId)
  if (tid === Number(policy.outgoing_therapist_user_id)) {
    return `Outgoing therapist: book through ${policy.outgoing_may_book_through}.`
  }
  if (tid === Number(policy.incoming_therapist_user_id)) {
    return `Incoming therapist: book from ${policy.incoming_may_book_from} onward.`
  }
  return null
}

export function normalizeBookingErrorMessage(message) {
  const text = String(message || '')
  if (text.includes('handover window') || text.includes('handover day')) {
    return TRANSITION_BOOKING_ERROR
  }
  if (text.includes('therapist transition') && text.includes('paused')) {
    return TRANSITION_HANDOVER_BANNER
  }
  return text || 'Could not complete booking.'
}
