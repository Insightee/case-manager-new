import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  applyServiceSelection,
  clearAllServices,
  enabledServiceIds,
  isGlobalFeatureEnabled,
  selectAllServices,
  setGlobalFeatureOverride,
  splitGrants,
} from './rbacEditorUtils.js'

const catalog = [{ id: 'homecare', label: 'Homecare' }, { id: 'shadow_support', label: 'Shadow' }]

describe('rbacEditorUtils', () => {
  it('selectAllServices enables all service ids and preserves org grants', () => {
    const grants = { billing: { enabled: true, access: 'write' } }
    const next = selectAllServices(grants, catalog, 'write')
    assert.deepEqual(enabledServiceIds(next, catalog), ['homecare', 'shadow_support'])
    assert.equal(next.billing?.enabled, true)
  })

  it('clearAllServices removes only service grants', () => {
    const grants = {
      homecare: { enabled: true, access: 'write' },
      billing: { enabled: true, access: 'view' },
    }
    const next = clearAllServices(grants)
    assert.deepEqual(enabledServiceIds(next, catalog), [])
    assert.equal(next.billing?.enabled, true)
  })

  it('applyServiceSelection replaces service set', () => {
    const grants = {
      homecare: { enabled: true, access: 'write' },
      shadow_support: { enabled: true, access: 'write' },
      billing: { enabled: true, access: 'write' },
    }
    const next = applyServiceSelection(grants, catalog, ['homecare'], 'view')
    assert.deepEqual(enabledServiceIds(next, catalog), ['homecare'])
    assert.equal(next.homecare.access, 'view')
    assert.equal(next.billing?.enabled, true)
  })

  it('setGlobalFeatureOverride syncs feature to all service ids', () => {
    const overrides = setGlobalFeatureOverride({}, ['homecare', 'shadow_support'], 'tickets', false)
    assert.deepEqual(overrides.homecare, ['tickets'])
    assert.deepEqual(overrides.shadow_support, ['tickets'])
    const restored = setGlobalFeatureOverride(overrides, ['homecare', 'shadow_support'], 'tickets', true)
    assert.deepEqual(restored.homecare, [])
    assert.deepEqual(restored.shadow_support, [])
  })

  it('isGlobalFeatureEnabled detects mixed overrides', () => {
    const overrides = { homecare: [], shadow_support: ['tickets'] }
    assert.equal(isGlobalFeatureEnabled(overrides, ['homecare', 'shadow_support'], 'tickets'), 'mixed')
    assert.equal(isGlobalFeatureEnabled(overrides, ['homecare', 'shadow_support'], 'cases'), true)
  })

  it('splitGrants separates org capabilities', () => {
    const { service, org } = splitGrants({ homecare: { enabled: true }, billing: { enabled: true } })
    assert.ok(service.homecare)
    assert.ok(org.billing)
  })
})
