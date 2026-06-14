import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  loginPathFromRoleName,
  portalHomePath,
  resolveAuthPortal,
  sessionMatchesLoginPage,
  SIGN_IN_PATH,
} from './portalLogin.js'

describe('portalLogin', () => {
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
