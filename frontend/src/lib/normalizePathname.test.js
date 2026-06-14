import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { normalizePathname } from './normalizePathname.js'

describe('normalizePathname', () => {
  it('removes zero-width space from portal login paths', () => {
    assert.equal(normalizePathname('/therapistlogin\u200B'), '/therapistlogin')
    assert.equal(normalizePathname('/clientlogin\u200B'), '/clientlogin')
    assert.equal(normalizePathname('/adminlogin\uFEFF'), '/adminlogin')
  })

  it('maps known portal aliases to canonical routes', () => {
    assert.equal(normalizePathname('/therapist-login'), '/therapistlogin')
    assert.equal(normalizePathname('/clinetlogin'), '/clientlogin')
    assert.equal(normalizePathname('/staff-login'), '/adminlogin')
    assert.equal(normalizePathname('/stafflogin'), '/adminlogin')
  })

  it('leaves normal paths unchanged', () => {
    assert.equal(normalizePathname('/therapistlogin'), '/therapistlogin')
    assert.equal(normalizePathname('/admin/cases'), '/admin/cases')
  })
})
