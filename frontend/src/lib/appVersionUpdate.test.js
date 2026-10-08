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
    'desktop-edge',
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
  assert.doesNotMatch(desktop.find((s) => s.id === 'remove')?.text || '', /edge:\/\/apps/i)
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

const BROWSER_UAS = {
  iphoneSafari:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
  iphoneStandalone:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
  iphoneChrome:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.54 Mobile/15E148 Safari/604.1',
  iphoneEdge:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 EdgiOS/126.0.2592.56 Mobile/15E148 Safari/605.1.15',
  androidChrome:
    'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
  androidEdge:
    'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 EdgA/126.0.2592.80',
  winChrome:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  winEdge:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.2592.87',
  macChrome:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  macEdge:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.2592.87',
  macSafari:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
}

test('detectReinstallPlatform for Chrome, Safari and Edge', () => {
  const mac = (userAgent) => ({ userAgent, platform: 'MacIntel', maxTouchPoints: 0 })
  assert.equal(detectReinstallPlatform(BROWSER_UAS.iphoneSafari), 'ios')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.iphoneStandalone), 'ios')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.iphoneChrome), 'ios-chrome')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.iphoneEdge), 'ios-edge')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.androidChrome), 'android')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.androidEdge), 'android-edge')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.winChrome), 'desktop')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.winEdge), 'desktop-edge')
  assert.equal(detectReinstallPlatform(mac(BROWSER_UAS.macChrome)), 'desktop')
  assert.equal(detectReinstallPlatform(mac(BROWSER_UAS.macEdge)), 'desktop-edge')
  assert.equal(detectReinstallPlatform(mac(BROWSER_UAS.macSafari)), 'mac-safari')
})

test('getReinstallSteps gives Chrome, Safari and Edge their own flow', () => {
  const ctx = { portalUrl: 'https://www.insighte.org/parent', appName: 'InsighteCase Client' }
  const text = (platform) =>
    getReinstallSteps(platform, ctx)
      .map((s) => `${s.label || ''} ${s.text || ''} ${s.hint || ''}`)
      .join(' | ')
  const actions = (platform) => getReinstallSteps(platform, ctx).map((s) => s.action).filter(Boolean)

  // iPhone: never desktop steps; Chrome/Edge users are not forced into Safari.
  for (const p of ['ios', 'ios-chrome', 'ios-edge']) {
    assert.match(text(p), /Add to Home Screen/)
    assert.doesNotMatch(text(p), /chrome:\/\/apps|edge:\/\/apps|Install app/)
  }
  assert.deepEqual(actions('ios'), ['copy', 'open_safari'])
  assert.match(text('ios-chrome'), /Open in Chrome/)
  assert.deepEqual(actions('ios-chrome'), ['copy', 'open_browser'])
  assert.match(text('ios-edge'), /Open in Edge/)
  assert.deepEqual(actions('ios-edge'), ['copy', 'open_browser'])

  assert.match(text('android'), /Open in Chrome/)
  assert.match(text('android'), /Install app/)
  assert.match(text('android-edge'), /Open in Edge/)
  assert.doesNotMatch(text('android-edge'), /Open in Chrome|chrome:\/\//)

  assert.match(text('mac-safari'), /Add to Dock/)
  assert.match(text('mac-safari'), /Open in Safari/)
  assert.doesNotMatch(text('mac-safari'), /chrome:\/\/apps|edge:\/\/apps|Edge|Chrome/)
  assert.deepEqual(actions('mac-safari'), ['copy', 'open_browser'])

  assert.match(text('desktop'), /chrome:\/\/apps/)
  assert.doesNotMatch(text('desktop'), /edge:\/\/apps|Add to Dock|Add to Home Screen/)
  assert.match(text('desktop-edge'), /edge:\/\/apps/)
  assert.match(text('desktop-edge'), /Install this site as an app/)
  assert.doesNotMatch(text('desktop-edge'), /chrome:\/\/apps|Add to Dock/)
})
