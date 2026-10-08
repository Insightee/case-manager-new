import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildIosSafariOpenUrl,
  detectReinstallPlatform,
  formatVersionNoticeLead,
  getReinstallSteps,
  isGenericNetworkError,
  isRemoteBuildNewer,
  shouldOfferReinstallFallback,
  shouldShowVersionNotice,
  VERSION_PRIOR_STALE_KEY,
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
  assert.equal(
    detectReinstallPlatform('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'),
    'ios',
  )
  assert.equal(
    detectReinstallPlatform({
      userAgent:
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
      platform: 'MacIntel',
      maxTouchPoints: 5,
    }),
    'ios',
  )
  assert.equal(detectReinstallPlatform('Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36'), 'android')
  assert.equal(
    detectReinstallPlatform('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'),
    'desktop',
  )
  assert.equal(
    detectReinstallPlatform(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ),
    'desktop',
  )
  assert.equal(
    detectReinstallPlatform({
      userAgent:
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      platform: 'MacIntel',
      maxTouchPoints: 0,
    }),
    'desktop',
  )
})

test('detectReinstallPlatform() with no args uses navigator when available', () => {
  // Node 21+ exposes a getter-only global navigator, so swap it via defineProperty.
  const originalDesc = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    writable: true,
    value: {
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
      platform: 'Linux x86_64',
      maxTouchPoints: 0,
    },
  })
  try {
    assert.equal(detectReinstallPlatform(), 'ios')
  } finally {
    if (originalDesc) Object.defineProperty(globalThis, 'navigator', originalDesc)
    else delete globalThis.navigator
  }
})

test('getReinstallSteps includes portal URL in copy step flow', () => {
  const ios = getReinstallSteps('ios', {
    portalUrl: 'https://www.insighte.org/parent',
    appName: 'InsighteCase Client',
  })
  assert.ok(ios.some((s) => s.action === 'copy'))
  assert.ok(ios.some((s) => s.action === 'open_safari'))

  const desktop = getReinstallSteps('desktop', {
    portalUrl: 'https://www.insighte.org/therapist',
    appName: 'InsighteCase Therapist',
  })
  assert.match(desktop.find((s) => s.id === 'remove')?.text || '', /chrome:\/\/apps/i)
})

test('shouldOfferReinstallFallback only after prior stale visit', () => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => store.get(k) ?? null,
    setItem: (k, v) => store.set(k, v),
    removeItem: (k) => store.delete(k),
  }
  store.delete(VERSION_PRIOR_STALE_KEY)
  assert.equal(shouldOfferReinstallFallback('i1008', true), false)
  assert.equal(shouldOfferReinstallFallback('i1008', true), true)
  assert.equal(shouldOfferReinstallFallback('i1008', false), false)
})

test('shouldShowVersionNotice when deployed label is newer', () => {
  const soft = shouldShowVersionNotice({
    embeddedReleaseLabel: 'i1006',
    remoteReleaseLabel: 'i1008',
    standalone: false,
  })
  assert.equal(soft.show, true)
  assert.equal(soft.remoteNewer, true)

  const none = shouldShowVersionNotice({
    embeddedReleaseLabel: 'i1008',
    remoteReleaseLabel: 'i1008',
  })
  assert.equal(none.show, false)
})

test('buildIosSafariOpenUrl', () => {
  assert.equal(
    buildIosSafariOpenUrl('https://www.insighte.org/therapist'),
    'x-safari-https://www.insighte.org/therapist',
  )
})
