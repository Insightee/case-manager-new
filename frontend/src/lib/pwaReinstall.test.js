import assert from 'node:assert/strict'
import test from 'node:test'

import {
  appendReinstallParam,
  buildAndroidBrowserIntentUrl,
  getRemoveAppOneLiner,
  isReinstallLanding,
  launchReinstallInBrowser,
} from './pwaReinstall.js'
import { detectReinstallPlatform } from './appVersionUpdate.js'

test('appendReinstallParam and isReinstallLanding', () => {
  const url = appendReinstallParam('https://www.insighte.org/therapist')
  assert.match(url, /reinstall=1/)
  assert.equal(isReinstallLanding('reinstall=1'), true)
  assert.equal(isReinstallLanding('reinstall=0'), false)
})

test('detectReinstallPlatform covers iPhone, iPad touch Mac, Android, desktop Chrome and Edge', () => {
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
  assert.equal(detectReinstallPlatform('Mozilla/5.0 (Linux; Android 14; Pixel 7)'), 'android')
  assert.equal(
    detectReinstallPlatform(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ),
    'desktop',
  )
  assert.equal(
    detectReinstallPlatform(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ),
    'desktop-edge',
  )
})

test('getRemoveAppOneLiner is short and platform-specific', () => {
  assert.match(getRemoveAppOneLiner('ios', 'InsighteCase Therapist'), /Remove App/)
  assert.match(getRemoveAppOneLiner('desktop', 'InsighteCase Therapist'), /chrome:\/\/apps|Uninstall/)
})

test('buildAndroidBrowserIntentUrl targets Chrome package', () => {
  const intent = buildAndroidBrowserIntentUrl('https://www.insighte.org/parent?reinstall=1')
  assert.match(intent, /intent:\/\/www\.insighte\.org/)
  assert.match(intent, /com\.android\.chrome/)
})

test('launchReinstallInBrowser uses intent on Android', () => {
  const original = globalThis.window
  let href = ''
  globalThis.window = {
    location: { href: '', assign: (v) => { href = v } },
    open: () => null,
  }
  Object.defineProperty(globalThis.window.location, 'href', {
    set(v) { href = v },
    get() { return href },
  })
  launchReinstallInBrowser('android', 'https://www.insighte.org/therapist')
  assert.match(href, /^intent:\/\//)
  globalThis.window = original
})
