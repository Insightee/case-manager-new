import test from 'node:test'
import assert from 'node:assert/strict'
import {
  BANNED_UI_STRINGS,
  GOAL_STATUS_BADGES,
  GOAL_USE_OPTIONS,
  emptyClinicalExtension,
  mergeClinicalExtension,
} from './clinicalEvidenceFields.js'

test('chip option maps expose stable ids', () => {
  assert.ok(GOAL_USE_OPTIONS.length >= 3)
  assert.ok(GOAL_STATUS_BADGES.active_iep_goal.label.includes('IEP'))
  const ids = new Set(GOAL_USE_OPTIONS.map((o) => o.id))
  assert.equal(ids.size, GOAL_USE_OPTIONS.length)
})

test('banned UI strings stay out of exported labels', () => {
  const haystack = [
    ...GOAL_USE_OPTIONS.map((o) => o.label),
    GOAL_STATUS_BADGES.candidate.label,
  ]
    .join(' ')
    .toLowerCase()
  for (const banned of BANNED_UI_STRINGS) {
    assert.equal(haystack.includes(banned.toLowerCase()), false, `found banned string: ${banned}`)
  }
})

test('mergeClinicalExtension marks human_selected provenance', () => {
  const merged = mergeClinicalExtension(emptyClinicalExtension(), {
    child_response: 'accepted',
    therapist_interpretation: 'continue',
  })
  assert.equal(merged.child_response, 'accepted')
  assert.equal(merged.field_provenance.child_response, 'human_selected')
  assert.equal(merged.field_provenance.therapist_interpretation, 'human_selected')
})

test('mergeClinicalExtension marks adaptation_note as human_written', () => {
  const merged = mergeClinicalExtension(emptyClinicalExtension(), {
    adaptation_note: 'Gave extra time before transition',
  })
  assert.equal(merged.field_provenance.adaptation_note, 'human_written')
})

test('shouldShowBarrierTypes and shouldShowAdaptation', async () => {
  const { shouldShowBarrierTypes, shouldShowAdaptation } = await import('./clinicalEvidenceFields.js')
  assert.equal(shouldShowBarrierTypes('barrier_present'), true)
  assert.equal(shouldShowBarrierTypes('supportive'), false)
  assert.equal(shouldShowAdaptation('PARTLY_HELPFUL', false), true)
  assert.equal(shouldShowAdaptation('HELPFUL', false), false)
  assert.equal(shouldShowAdaptation(null, true), true)
})
