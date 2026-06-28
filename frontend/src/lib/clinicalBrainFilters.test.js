import assert from 'node:assert/strict'
import test from 'node:test'
import { applyClinicalFilters, EMPTY_FILTERS } from './clinicalBrainFilters.js'
import { mapRepositoryGoalStatus, evidenceLabelFromCount } from './clinicalBrainStatus.js'
import { filterParentSafeGoals } from './clinicalBrainPermissions.js'

test('applyClinicalFilters filters by domain', () => {
  const items = [
    { id: 1, label: 'AAC goal', domain_key: 'communication_aac' },
    { id: 2, label: 'Peer goal', domain_key: 'peer_social' },
  ]
  const filtered = applyClinicalFilters(items, { ...EMPTY_FILTERS, domain: 'communication_aac' })
  assert.equal(filtered.length, 1)
  assert.equal(filtered[0].id, 1)
})

test('mapRepositoryGoalStatus maps pending review', () => {
  const status = mapRepositoryGoalStatus({
    case_id: 1,
    status: 'candidate',
    lifecycle_status: 'pending_review',
  })
  assert.equal(status.id, 'sent_for_review')
})

test('evidenceLabelFromCount tiers', () => {
  assert.equal(evidenceLabelFromCount(0), 'new')
  assert.equal(evidenceLabelFromCount(3), 'emerging')
  assert.equal(evidenceLabelFromCount(6), 'commonly_used')
})

test('filterParentSafeGoals hides internal', () => {
  const items = [
    { id: 1, parent_safe: true },
    { id: 2, visibility: 'internal_only' },
  ]
  assert.equal(filterParentSafeGoals(items).length, 1)
})
