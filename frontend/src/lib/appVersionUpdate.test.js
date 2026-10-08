import assert from 'node:assert/strict'
import test from 'node:test'

import {
  detectReinstallPlatform,
  formatVersionNoticeLead,
  getReinstallSteps,
  isGenericNetworkError,
  isRemoteBuildNewer,
  shouldShowVersionNotice,
} from './appVersionUpdate.js'

test('isRemoteBuildNewer compares release labels', () => {
  assert.equal(isRemoteBuildNewer('i1006', 'i1008'), true)
  assert.equal(isRemoteBuildNewer('i1008', 'i1008'), false)
  assert.equal(isRemoteBuildNewer('dev', 'i1008'), false)
})

test('isGenericNetworkError matches Safari generic failures only as network', () => {
  assert.equal(isGenericNetworkError(new Error('Load failed')), true)
  assert.equal(isGenericNetworkError(new Error('Failed to fetch')), true)
  assert.equal(isGenericNetworkError(new Error('Failed to fetch dynamically imported module')), false)
})

test('formatVersionNoticeLead', () => {
  assert.match(formatVersionNoticeLead('i1006', 'i1008'), /You're on i1006, latest is i1008/)
})

test('detectReinstallPlatform', () => {
  assert.equal(detectReinstallPlatform('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'), 'ios')
  assert.equal(detectReinstallPlatform('Mozilla/5.0 (Linux; Android 14)'), 'android')
})

test('getReinstallSteps includes portal URL', () => {
  const ios = getReinstallSteps('ios', {
    portalUrl: 'https://www.insighte.org/parent',
    appName: 'InsighteCase Client',
  })
  assert.equal(ios.length, 3)
  assert.match(ios[1], /insighte\.org\/parent/)
})

test('shouldShowVersionNotice only when deployed label is newer', () => {
  const soft = shouldShowVersionNotice({
    embeddedReleaseLabel: 'i1006',
    remoteReleaseLabel: 'i1008',
    standalone: false,
  })
  assert.equal(soft.show, true)
  assert.equal(soft.mode, 'soft')

  const none = shouldShowVersionNotice({
    embeddedReleaseLabel: 'i1008',
    remoteReleaseLabel: 'i1008',
    chunkStale: true,
    swWaiting: true,
  })
  assert.equal(none.show, false)

  const noRemote = shouldShowVersionNotice({
    embeddedReleaseLabel: 'i1008',
    remoteReleaseLabel: null,
    chunkStale: true,
  })
  assert.equal(noRemote.show, false)
})
