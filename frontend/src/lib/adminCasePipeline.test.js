import assert from 'node:assert/strict'
import test from 'node:test'
import {
  caseStateFromLegacyStatus,
  filterPipelineRows,
  filterPipelineRowsForQueueCounts,
  matchesCaseState,
  normalizeCaseState,
  pipelineQueueCounts,
} from './adminCasePipeline.js'

const sampleRows = [
  { id: 1, case_code: 'A1', status: 'ACTIVE', pipeline_column: 'iep', product_module: 'homecare' },
  { id: 2, case_code: 'A2', status: 'ACTIVE', pipeline_column: 'active', product_module: 'homecare' },
  { id: 3, case_code: 'C1', status: 'CLOSED', pipeline_column: 'closed', product_module: 'homecare' },
  { id: 4, case_code: 'P1', status: 'PENDING_ALLOTMENT', pipeline_column: 'pending_allotment', product_module: 'homecare' },
]

test('normalizeCaseState maps legacy active alias to pipeline_active', () => {
  assert.equal(normalizeCaseState('active'), 'pipeline_active')
  assert.equal(normalizeCaseState('status_active'), 'status_active')
})

test('caseStateFromLegacyStatus maps ACTIVE to status_active', () => {
  assert.equal(caseStateFromLegacyStatus('ACTIVE'), 'status_active')
})

test('matchesCaseState status_active matches ACTIVE status in any pipeline column', () => {
  assert.equal(matchesCaseState(sampleRows[0], 'status_active'), true)
  assert.equal(matchesCaseState(sampleRows[2], 'status_active'), false)
})

test('matchesCaseState pipeline_active matches only clean active column', () => {
  assert.equal(matchesCaseState(sampleRows[0], 'pipeline_active'), false)
  assert.equal(matchesCaseState(sampleRows[1], 'pipeline_active'), true)
})

test('filterPipelineRowsForQueueCounts ignores case state for tab badges', () => {
  const filtered = filterPipelineRowsForQueueCounts(sampleRows, {
    caseState: 'pipeline_active',
    queue: 'all',
  })
  const counts = pipelineQueueCounts(filtered)
  assert.equal(counts.all, sampleRows.length)
  assert.equal(counts.needs_action, 2)
  assert.equal(counts.allotment, 1)
})

test('filterPipelineRows applies case state and queue together', () => {
  const statusActive = filterPipelineRows(sampleRows, { caseState: 'status_active', queue: 'all' })
  assert.equal(statusActive.length, 2)

  const pipelineActiveNeedsAction = filterPipelineRows(sampleRows, {
    caseState: 'pipeline_active',
    queue: 'needs_action',
  })
  assert.equal(pipelineActiveNeedsAction.length, 0)
})
