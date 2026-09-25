import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_SIGN_IN_PATH,
  loginPathFromRoleName,
  portalHomePath,
  portalLoginPath,
  resolveAuthPortal,
  sessionMatchesLoginPage,
  SIGN_IN_PATH,
} from './portalLogin.js'

describe('portalLogin', () => {
  it('defaults unknown portal sign-in to the portal picker', () => {
    assert.equal(DEFAULT_SIGN_IN_PATH, '/login')
    assert.equal(portalLoginPath(null), '/login')
    assert.equal(portalLoginPath(undefined), '/login')
  })

  it('maps invite sign-in links to the correct portal login page', () => {
    assert.equal(loginPathFromRoleName('PARENT'), SIGN_IN_PATH.parent)
    assert.equal(loginPathFromRoleName('THERAPIST'), SIGN_IN_PATH.therapist)
    assert.equal(loginPathFromRoleName('HR'), SIGN_IN_PATH.admin)
    assert.equal(loginPathFromRoleName('MODULE_ADMIN'), SIGN_IN_PATH.admin)
  })

  it('routes users home by role after invite acceptance', () => {
    assert.equal(portalHomePath({ roles: ['PARENT'] }), '/parent')
    assert.equal(portalHomePath({ roles: ['THERAPIST'] }), '/therapist')
    assert.equal(portalHomePath({ roles: ['HR'] }), '/admin')
    assert.equal(portalHomePath({ roles: ['CASE_MANAGER'] }), '/admin')
    assert.equal(portalHomePath({ roles: ['SPOT'] }), '/admin')
  })

  it('maps SPOT to the admin sign-in page', () => {
    assert.equal(loginPathFromRoleName('SPOT'), SIGN_IN_PATH.admin)
    assert.equal(resolveAuthPortal({ roles: ['SPOT'] }, 'admin'), 'admin')
  })

  it('ignores stale portal selection when inferring home route', () => {
    const parent = { roles: ['PARENT'] }
    assert.equal(resolveAuthPortal(parent, 'admin'), 'parent')
    assert.equal(portalHomePath(parent), '/parent')
  })

  it('matches portal-bound sessions to the login page that created them', () => {
    const parent = { roles: ['PARENT'] }
    assert.equal(sessionMatchesLoginPage(parent, 'parent', 'parent'), true)
    assert.equal(sessionMatchesLoginPage(parent, 'admin', 'parent'), false)
    assert.equal(sessionMatchesLoginPage(parent, 'parent', 'admin'), false)
  })
})
