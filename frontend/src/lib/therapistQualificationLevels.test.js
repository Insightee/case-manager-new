import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  PROFILE_COMPLETION_DEADLINE_ISO,
  PROFILE_COMPLETION_EDIT_PATH,
  isProfileCompletionIncomplete,
} from './therapistQualificationLevels.js'

describe('profile completion reminder', () => {
  it('uses 3 October 2026 and the profile edit deep link', () => {
    assert.equal(PROFILE_COMPLETION_DEADLINE_ISO, '2026-10-03')
    assert.equal(PROFILE_COMPLETION_EDIT_PATH, '/therapist/profile?edit=1')
  })

  it('does not treat a missing completion block as incomplete', () => {
    assert.equal(isProfileCompletionIncomplete(null), false)
    assert.equal(isProfileCompletionIncomplete({ complete: true }), false)
    assert.equal(isProfileCompletionIncomplete({ complete: false, percent: 40 }), true)
  })
})
