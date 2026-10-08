import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getCanonicalPortalUrl,
  resolveCanonicalAppOrigin,
} from './canonicalAppUrl.js'

test('resolveCanonicalAppOrigin prefers VITE_APP_ORIGIN', () => {
  const origin = resolveCanonicalAppOrigin({
    hostname: 'localhost',
    protocol: 'http:',
  })
  assert.equal(typeof origin, 'string')
  assert.ok(origin.length > 0)
})

test('getCanonicalPortalUrl uses manifest paths', () => {
  const url = getCanonicalPortalUrl('therapist', {
    origin: 'https://www.insighte.org',
  })
  assert.equal(url, 'https://www.insighte.org/therapist')
})

test('apex insighte.org resolves to www', () => {
  const origin = resolveCanonicalAppOrigin({ hostname: 'insighte.org', protocol: 'https:' })
  assert.equal(origin, 'https://www.insighte.org')
})
