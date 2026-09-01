import assert from 'node:assert/strict'
import test from 'node:test'
import {
  canShowPortalAppActions,
  portalAppMenuItems,
  primaryPortalAppAction,
} from './portalAppActions.js'

const config = { appName: 'InsighteCase Therapist' }

test('primary action is install in the browser and refresh in the installed app', () => {
  assert.equal(primaryPortalAppAction({ standalone: false }), 'install')
  assert.equal(primaryPortalAppAction({ standalone: true }), 'refresh')
})

test('menu always includes install and refresh, primary first', () => {
  assert.deepEqual(portalAppMenuItems('install'), ['install', 'refresh'])
  assert.deepEqual(portalAppMenuItems('refresh'), ['refresh', 'install'])
})

test('banner hides after install; topbar stays so refresh remains available', () => {
  assert.equal(
    canShowPortalAppActions('banner', { config, installed: true, isMobilePortal: true }),
    false,
  )
  assert.equal(
    canShowPortalAppActions('banner', { config, installed: false, isMobilePortal: true }),
    true,
  )
  assert.equal(
    canShowPortalAppActions('topbar', { config, installed: true, isMobilePortal: false }),
    true,
  )
  assert.equal(
    canShowPortalAppActions('sidebar', { config, installed: true, canNativeInstall: false }),
    true,
  )
})

test('browser topbar still requires an install-capable surface', () => {
  assert.equal(
    canShowPortalAppActions('topbar', {
      config,
      installed: false,
      isMobilePortal: false,
      canNativeInstall: false,
      iosSafari: false,
      macSafari: false,
    }),
    false,
  )
  assert.equal(
    canShowPortalAppActions('topbar', {
      config,
      installed: false,
      isMobilePortal: true,
    }),
    true,
  )
})

test('no portal config hides every surface', () => {
  assert.equal(canShowPortalAppActions('topbar', { installed: true }), false)
})
