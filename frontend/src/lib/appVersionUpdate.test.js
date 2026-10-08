import assert from 'node:assert/strict'
import test from 'node:test'

import {
  detectReinstallPlatform,
  getReinstallSteps,
  isGenericNetworkError,
  isRemoteBuildNewer,
  shouldShowVersionNotice,
} from './appVersionUpdate.js'

test('isRemoteBuildNewer ignores dev and matching ids', () => {
  assert.equal(isRemoteBuildNewer('dev', 'abc'), false)
  assert.equal(isRemoteBuildNewer('abc', 'abc'), false)
  assert.equal(isRemoteBuildNewer('abc', 'def'), true)
})

test('isGenericNetworkError matches Safari generic failures only as network', () => {
  assert.equal(isGenericNetworkError(new Error('Load failed')), true)
  assert.equal(isGenericNetworkError(new Error('Failed to fetch')), true)
  assert.equal(isGenericNetworkError(new Error('Failed to fetch dynamically imported module')), false)
})

test('detectReinstallPlatform', () => {
  assert.equal(detectReinstallPlatform('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'), 'ios')
  assert.equal(detectReinstallPlatform('Mozilla/5.0 (Linux; Android 14)'), 'android')
  assert.equal(detectReinstallPlatform('Mozilla/5.0 (Windows NT 10.0)'), 'other')
})

test('getReinstallSteps includes portal URL', () => {
  const ios = getReinstallSteps('ios', {
    portalUrl: 'https://www.insighte.org/parent',
    appName: 'InsighteCase Client',
  })
  assert.equal(ios.length, 3)
  assert.match(ios[1], /insighte\.org\/parent/)
  const android = getReinstallSteps('android', {
    portalUrl: 'https://www.insighte.org/therapist',
    appName: 'InsighteCase Therapist',
  })
  assert.match(android[2], /Install app/)
})

test('shouldShowVersionNotice respects dismiss and hard mode', () => {
  const soft = shouldShowVersionNotice({
    embeddedBuildId: 'a',
    remoteBuildId: 'b',
    standalone: false,
  })
  assert.equal(soft.show, true)
  assert.equal(soft.mode, 'soft')

  const none = shouldShowVersionNotice({
    embeddedBuildId: 'same',
    remoteBuildId: 'same',
    chunkStale: false,
    swWaiting: false,
  })
  assert.equal(none.show, false)
})
