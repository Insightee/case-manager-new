import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_PARENT_EMAIL_PREFERENCES,
  emailPreferencesFromApi,
  PARENT_EMAIL_PREFERENCE_OPTIONS,
} from './parentEmailPreferenceUtils.js'

describe('parent email preference utils', () => {
  it('defaults all categories on', () => {
    assert.equal(DEFAULT_PARENT_EMAIL_PREFERENCES.appointments, true)
    assert.equal(DEFAULT_PARENT_EMAIL_PREFERENCES.reports, true)
    assert.equal(DEFAULT_PARENT_EMAIL_PREFERENCES.incidents, true)
  })

  it('treats missing API values as on', () => {
    const prefs = emailPreferencesFromApi({ session_logs: true }, true)
    assert.equal(prefs.appointments, true)
    assert.equal(prefs.reports, true)
  })

  it('labels same-day appointments category', () => {
    const row = PARENT_EMAIL_PREFERENCE_OPTIONS.find((o) => o.key === 'appointments')
    assert.ok(row?.label.includes('Same-day'))
  })
})
