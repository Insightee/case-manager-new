import assert from 'node:assert/strict'
import test from 'node:test'
import {
  caseStateFromLegacyStatus,
  countActivePipelineFilters,
  deriveOpenedYearOptions,
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
  { id: 5, case_code: 'N1', status: 'ACTIVE', pipeline_column: 'needs_therapist', product_module: 'homecare' },
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
  assert.equal(counts.needs_action, 3)
  assert.equal(counts.allotment, 2)
})

test('filterPipelineRows allotment queue includes needs_therapist', () => {
  const rows = filterPipelineRows(sampleRows, { queue: 'allotment' })
  assert.deepEqual(
    rows.map((r) => r.case_code).sort(),
    ['N1', 'P1'],
  )
})

const datedRows = [
  { id: 10, case_code: 'D1', status: 'ACTIVE', pipeline_column: 'active', created_at: '2026-08-12T09:00:00Z' },
  { id: 11, case_code: 'D2', status: 'ACTIVE', pipeline_column: 'active', created_at: '2026-03-04T09:00:00Z' },
  { id: 12, case_code: 'D3', status: 'ACTIVE', pipeline_column: 'active', created_at: '2025-08-20T09:00:00Z' },
]

test('filterPipelineRows narrows by opened year', () => {
  const rows = filterPipelineRows(datedRows, { queue: 'all', openedYear: '2026' })
  assert.deepEqual(rows.map((r) => r.case_code).sort(), ['D1', 'D2'])
})

test('filterPipelineRows narrows by opened month across years', () => {
  const rows = filterPipelineRows(datedRows, { queue: 'all', openedMonth: '08' })
  assert.deepEqual(rows.map((r) => r.case_code).sort(), ['D1', 'D3'])
})

test('filterPipelineRows combines opened month and year', () => {
  const rows = filterPipelineRows(datedRows, { queue: 'all', openedMonth: '08', openedYear: '2026' })
  assert.deepEqual(rows.map((r) => r.case_code), ['D1'])
})

test('deriveOpenedYearOptions returns distinct years newest first', () => {
  const opts = deriveOpenedYearOptions(datedRows)
  assert.deepEqual(opts.map((o) => o.value), ['all', '2026', '2025'])
})

test('countActivePipelineFilters counts month and year selections', () => {
  assert.equal(countActivePipelineFilters({ openedMonth: '08', openedYear: '2026' }), 2)
  assert.equal(countActivePipelineFilters({}), 0)
})

test('filterPipelineRows applies case state and queue together', () => {
  const statusActive = filterPipelineRows(sampleRows, { caseState: 'status_active', queue: 'all' })
  assert.equal(statusActive.length, 3)

  const pipelineActiveNeedsAction = filterPipelineRows(sampleRows, {
    caseState: 'pipeline_active',
    queue: 'needs_action',
  })
  assert.equal(pipelineActiveNeedsAction.length, 0)
})
