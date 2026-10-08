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

const BROWSER_UAS = {
  iphoneSafari:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
  iphoneChrome:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.54 Mobile/15E148 Safari/604.1',
  iphoneStandalone:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
  samsung:
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36',
  androidFirefox: 'Mozilla/5.0 (Android 14; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0',
  // Brave sends a plain Chrome UA on Android and desktop.
  androidBrave:
    'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
  desktopFirefox: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
  macFirefox: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:128.0) Gecko/20100101 Firefox/128.0',
  desktopBrave:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  macChrome:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  macSafari:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
}

test('detectReinstallPlatform per browser', () => {
  const mac = (userAgent) => ({ userAgent, platform: 'MacIntel', maxTouchPoints: 0 })
  assert.equal(detectReinstallPlatform(BROWSER_UAS.iphoneSafari), 'ios')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.iphoneChrome), 'ios')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.iphoneStandalone), 'ios')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.samsung), 'android-samsung')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.androidFirefox), 'android-firefox')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.androidBrave), 'android')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.desktopFirefox), 'desktop-firefox')
  assert.equal(detectReinstallPlatform(mac(BROWSER_UAS.macFirefox)), 'desktop-firefox')
  assert.equal(detectReinstallPlatform(BROWSER_UAS.desktopBrave), 'desktop')
  assert.equal(detectReinstallPlatform(mac(BROWSER_UAS.macChrome)), 'desktop')
  assert.equal(detectReinstallPlatform(mac(BROWSER_UAS.macSafari)), 'mac-safari')
})

test('getReinstallSteps gives each browser its own flow', () => {
  const ctx = { portalUrl: 'https://www.insighte.org/parent', appName: 'InsighteCase Client' }
  const text = (platform) =>
    getReinstallSteps(platform, ctx)
      .map((s) => `${s.label || ''} ${s.text || ''} ${s.hint || ''}`)
      .join(' | ')
  const actions = (platform) => getReinstallSteps(platform, ctx).map((s) => s.action).filter(Boolean)

  // iPhone (any browser): Safari primary, Chrome/Edge mentioned, never desktop steps.
  assert.match(text('ios'), /Add to Home Screen/)
  assert.match(text('ios'), /Chrome or Edge/)
  assert.doesNotMatch(text('ios'), /chrome:\/\/apps|Install app/)
  assert.deepEqual(actions('ios'), ['copy', 'open_safari'])

  assert.match(text('android-samsung'), /Samsung Internet/)
  assert.match(text('android-samsung'), /Add page to → Home screen/)
  assert.doesNotMatch(text('android-samsung'), /Open in Chrome|chrome:\/\/apps/)

  assert.match(text('android-firefox'), /Open in Firefox/)
  assert.doesNotMatch(text('android-firefox'), /Open in Chrome|chrome:\/\/apps/)

  assert.match(text('android'), /Open in browser/)
  assert.match(text('android'), /Brave/)

  assert.match(text('mac-safari'), /Add to Dock/)
  assert.match(text('mac-safari'), /Open in Safari/)
  assert.doesNotMatch(text('mac-safari'), /chrome:\/\/apps|Edge|Chrome/)
  assert.deepEqual(actions('mac-safari'), ['copy', 'open_browser'])

  assert.match(text('desktop-firefox'), /bookmark/)
  assert.doesNotMatch(text('desktop-firefox'), /chrome:\/\/apps/)

  assert.match(text('desktop'), /chrome:\/\/apps/)
  assert.match(text('desktop'), /brave:\/\/apps/)
  assert.doesNotMatch(text('desktop'), /Add to Dock|Add to Home Screen/)
})
