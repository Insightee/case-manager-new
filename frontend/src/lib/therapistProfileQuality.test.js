import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  addQualificationEntry,
  evaluateProfileQuality,
  isProfileNudgeNeeded,
  QUALITY_REMINDERS,
  removeQualificationEntry,
  submitHelperText,
  wordCount,
} from './therapistProfileQuality.js'

const FORTY_ONE = Array.from({ length: 41 }, () => 'support').join(' ')

describe('therapist profile quality', () => {
  it('counts words and scores a complete listing as auto-pass', () => {
    assert.equal(wordCount(FORTY_ONE), 41)
    const quality = evaluateProfileQuality({
      email: 't@demo.com',
      phone: '9876543210',
      avatarUrl: '/avatars/1',
      addressLine1: '12 MG Road',
      city: 'Bengaluru',
      pincode: '560001',
      displayName: 'Neha',
      shortBio: FORTY_ONE,
      servicesOffered: ['homecare'],
      qualificationEntries: [{ kind: 'degree', title: 'M.Sc.', year: 2019 }],
    })
    assert.equal(quality.percent, 100)
    assert.equal(quality.auto_pass, true)
    assert.equal(submitHelperText(quality), 'This will publish now.')
  })

  it('keeps auto-pass off without a degree', () => {
    const quality = evaluateProfileQuality({
      email: 't@demo.com',
      phone: '9876543210',
      avatarUrl: '/avatars/1',
      addressLine1: '12 MG Road',
      city: 'Bengaluru',
      pincode: '560001',
      displayName: 'Neha',
      shortBio: FORTY_ONE,
      servicesOffered: ['homecare'],
      qualificationEntries: [],
    })
    assert.equal(quality.auto_pass, false)
    assert.match(quality.reminders[0].message, /degree/i)
  })

  it('uses needs_nudge when present', () => {
    assert.equal(isProfileNudgeNeeded({ complete: false, needs_nudge: false }), false)
    assert.equal(isProfileNudgeNeeded({ complete: false, needs_nudge: true }), true)
    assert.equal(isProfileNudgeNeeded({ complete: false }), true)
  })

  it('keeps reminder copy and submit helper text', () => {
    assert.match(QUALITY_REMINDERS.short_bio, /more than 40 words/)
    assert.match(QUALITY_REMINDERS.pincode, /6-digit pincode/)
    assert.match(QUALITY_REMINDERS.degree, /one degree/)
    const blocked = evaluateProfileQuality({ displayName: 'Neha', servicesOffered: ['homecare'] })
    assert.equal(submitHelperText(blocked), 'Looks like we still need a few details before we can send this for review.')
    const reviewable = evaluateProfileQuality({
      email: 't@demo.com',
      phone: '9876543210',
      addressLine1: '12 MG Road',
      city: 'Bengaluru',
      pincode: '560001',
      displayName: 'Neha',
      servicesOffered: ['homecare'],
      qualificationEntries: [{ kind: 'degree', title: 'B.Ed', year: 2018 }],
    })
    assert.equal(reviewable.can_submit, true)
    assert.equal(
      submitHelperText(reviewable),
      'You can send this for admin review, or add a few more details to publish now.',
    )
  })

  it('adds and removes qualification cards', () => {
    const withDegree = addQualificationEntry([], { kind: 'degree', title: 'M.Sc. Psychology', year: '2019' })
    assert.deepEqual(withDegree, [{ kind: 'degree', title: 'M.Sc. Psychology', year: 2019 }])
    const withCert = addQualificationEntry(withDegree, { kind: 'certificate', title: 'RCI', year: 2021 })
    assert.equal(withCert.length, 2)
    assert.deepEqual(removeQualificationEntry(withCert, 0), [{ kind: 'certificate', title: 'RCI', year: 2021 }])
    assert.deepEqual(addQualificationEntry(withDegree, { kind: 'degree', title: '', year: 2019 }), withDegree)
  })
})
