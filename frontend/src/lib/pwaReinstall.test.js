import assert from 'node:assert/strict'
import test from 'node:test'

import {
  appendReinstallParam,
  buildAndroidBrowserIntentUrl,
  getInstalledMessage,
  getManualAddLine,
  getRemoveAppOneLiner,
  isReinstallLanding,
  launchReinstallInBrowser,
  portalFromPath,
  stripReinstallParam,
  supportsOneTapInstall,
} from './pwaReinstall.js'
import { detectReinstallPlatform } from './appVersionUpdate.js'

test('appendReinstallParam and isReinstallLanding treat the flag as a strict boolean', () => {
  const url = appendReinstallParam('https://www.insighte.org/therapist')
  assert.equal(url, 'https://www.insighte.org/therapist?reinstall=1')
  assert.equal(isReinstallLanding('reinstall=1'), true)
  assert.equal(isReinstallLanding('?reinstall=1'), true)
  assert.equal(isReinstallLanding('reinstall=0'), false)
  assert.equal(isReinstallLanding('reinstall=https://evil.example'), false)
  assert.equal(isReinstallLanding(''), false)
})

test('stripReinstallParam keeps other params and the path', () => {
  assert.equal(stripReinstallParam('https://www.insighte.org/parent?reinstall=1'), '/parent')
  assert.equal(stripReinstallParam('https://www.insighte.org/parent?tab=a&reinstall=1#x'), '/parent?tab=a#x')
})

test('portalFromPath maps portal and login paths only', () => {
  assert.equal(portalFromPath('/therapist'), 'therapist')
  assert.equal(portalFromPath('/therapistlogin'), 'therapist')
  assert.equal(portalFromPath('/parent/home'), 'parent')
  assert.equal(portalFromPath('/clientlogin'), 'parent')
  assert.equal(portalFromPath('/admin/people'), 'admin')
  assert.equal(portalFromPath('/adminlogin'), 'admin')
  assert.equal(portalFromPath('/therapistsomething'), null)
  assert.equal(portalFromPath('/login'), null)
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

test('one-tap install only where Chrome/Edge expose beforeinstallprompt', () => {
  assert.equal(supportsOneTapInstall('android'), true)
  assert.equal(supportsOneTapInstall('android-edge'), true)
  assert.equal(supportsOneTapInstall('desktop'), true)
  assert.equal(supportsOneTapInstall('desktop-edge'), true)
  assert.equal(supportsOneTapInstall('ios'), false)
  assert.equal(supportsOneTapInstall('ios-chrome'), false)
  assert.equal(supportsOneTapInstall('mac-safari'), false)
})

test('copy is platform-specific and plain', () => {
  assert.match(getRemoveAppOneLiner('ios', 'InsighteCase Therapist'), /Press and hold the old InsighteCase Therapist icon/)
  assert.match(getRemoveAppOneLiner('android', 'X'), /Uninstall/)
  assert.match(getRemoveAppOneLiner('desktop', 'X'), /⋮/)
  assert.match(getRemoveAppOneLiner('desktop-edge', 'X'), /…/)
  assert.doesNotMatch(getRemoveAppOneLiner('mac-safari', 'X'), /chrome:\/\//)
  assert.match(getManualAddLine('ios'), /Share button, then Add to Home Screen/)
  assert.match(getManualAddLine('ios-chrome'), /address bar/)
  assert.match(getManualAddLine('mac-safari'), /Add to Dock/)
  assert.match(getInstalledMessage('android'), /^Installed\. Open InsighteCase from your home screen\.$/)
  assert.match(getInstalledMessage('desktop-edge'), /desktop/)
})

test('buildAndroidBrowserIntentUrl targets the browser package with a canonical https fallback', () => {
  const intent = buildAndroidBrowserIntentUrl('https://www.insighte.org/parent?reinstall=1')
  assert.match(intent, /^intent:\/\/www\.insighte\.org\/parent\?reinstall=1#Intent;scheme=https;/)
  assert.match(intent, /package=com\.android\.chrome;/)
  assert.match(intent, /S\.browser_fallback_url=https%3A%2F%2Fwww\.insighte\.org%2Fparent%3Freinstall%3D1;end$/)
  assert.match(
    buildAndroidBrowserIntentUrl('https://www.insighte.org/parent?reinstall=1', 'com.microsoft.emmx'),
    /package=com\.microsoft\.emmx;/,
  )
  assert.match(buildAndroidBrowserIntentUrl('https://www.insighte.org/x', 'evil;package=x'), /package=com\.android\.chrome;/)
  assert.throws(() => buildAndroidBrowserIntentUrl('javascript:alert(1)'))
  assert.throws(() => buildAndroidBrowserIntentUrl('http://www.insighte.org/parent'))
})

test('launchReinstallInBrowser opens only the canonical portal URL per platform', () => {
  const calls = []
  const nav = { assign: (u) => calls.push(['assign', u]), open: (...a) => calls.push(['open', ...a]) }
  launchReinstallInBrowser('android', 'therapist', nav)
  launchReinstallInBrowser('android-edge', 'parent', nav)
  launchReinstallInBrowser('ios', 'admin', nav)
  launchReinstallInBrowser('desktop', 'therapist', nav)
  launchReinstallInBrowser('desktop-edge', 'bogus', nav)
  assert.match(calls[0][1], /^intent:\/\/[^/]+\/therapist\?reinstall=1#Intent;.*package=com\.android\.chrome;/)
  assert.match(calls[1][1], /package=com\.microsoft\.emmx;/)
  assert.match(calls[2][1], /^x-safari-https:\/\/[^/]+\/admin\?reinstall=1$/)
  assert.deepEqual(calls[3].slice(2), ['_blank', 'noopener,noreferrer'])
  assert.match(calls[3][1], /^https?:\/\/[^/]+\/therapist\?reinstall=1$/)
  assert.match(calls[4][1], /\/parent\?reinstall=1$/)
})
