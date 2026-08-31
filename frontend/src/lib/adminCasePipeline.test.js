import assert from 'node:assert/strict'
import { describe, it, test } from 'node:test'
import {
  buildPipelineActions,
  caseStateFromLegacyStatus,
  countActivePipelineFilters,
  defaultOpenedRange,
  defaultPipelineFilters,
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

const datedSampleRows = [
  {
    id: 1,
    case_code: 'IC-2026-001',
    child_name: 'Alpha',
    status: 'ACTIVE',
    pipeline_column: 'active',
    product_module: 'homecare',
    created_at: '2026-08-15T10:00:00Z',
    therapist_user_id: 10,
    case_manager_user_id: 20,
    child_id: 100,
  },
  {
    id: 2,
    case_code: 'IC-2026-002',
    child_name: 'Beta',
    status: 'ACTIVE',
    pipeline_column: 'reports_logs',
    product_module: 'shadow_support',
    created_at: '2026-07-01T10:00:00Z',
    therapist_user_id: 11,
    case_manager_user_id: 20,
    child_id: 101,
    missing_logs: 1,
  },
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
    openedPreset: 'all',
  })
  const counts = pipelineQueueCounts(filtered)
  assert.equal(counts.all, sampleRows.length)
  assert.equal(counts.needs_action, 3)
  assert.equal(counts.allotment, 2)
})

test('filterPipelineRows allotment queue includes needs_therapist', () => {
  const rows = filterPipelineRows(sampleRows, { queue: 'allotment', openedPreset: 'all' })
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
  const rows = filterPipelineRows(datedRows, { ...defaultPipelineFilters(), queue: 'all', openedYear: '2026', openedPreset: 'all' })
  assert.deepEqual(rows.map((r) => r.case_code).sort(), ['D1', 'D2'])
})

test('filterPipelineRows narrows by opened month across years', () => {
  const rows = filterPipelineRows(datedRows, { ...defaultPipelineFilters(), queue: 'all', openedMonth: '08', openedPreset: 'all' })
  assert.deepEqual(rows.map((r) => r.case_code).sort(), ['D1', 'D3'])
})

test('filterPipelineRows combines opened month and year', () => {
  const rows = filterPipelineRows(datedRows, {
    ...defaultPipelineFilters(),
    queue: 'all',
    openedMonth: '08',
    openedYear: '2026',
    openedPreset: 'all',
  })
  assert.deepEqual(rows.map((r) => r.case_code), ['D1'])
})

test('deriveOpenedYearOptions returns distinct years newest first', () => {
  const opts = deriveOpenedYearOptions(datedRows)
  assert.deepEqual(opts.map((o) => o.value), ['all', '2026', '2025'])
})

test('countActivePipelineFilters counts month and year selections', () => {
  assert.equal(countActivePipelineFilters({ openedMonth: '08', openedYear: '2026' }), 2)
  assert.equal(countActivePipelineFilters(defaultPipelineFilters()), 0)
})

test('filterPipelineRows applies case state and queue together', () => {
  const statusActive = filterPipelineRows(sampleRows, { caseState: 'status_active', queue: 'all', openedPreset: 'all' })
  assert.equal(statusActive.length, 3)

  const pipelineActiveNeedsAction = filterPipelineRows(sampleRows, {
    caseState: 'pipeline_active',
    queue: 'needs_action',
    openedPreset: 'all',
  })
  assert.equal(pipelineActiveNeedsAction.length, 0)
})

describe('defaultOpenedRange', () => {
  it('returns first of month through reference day', () => {
    const range = defaultOpenedRange(new Date('2026-08-29T12:00:00Z'))
    assert.equal(range.from, '2026-08-01')
    assert.equal(range.to, '2026-08-29')
  })
})

describe('filterPipelineRows opened date range', () => {
  it('defaults to current month window', () => {
    const filters = defaultPipelineFilters()
    const rows = filterPipelineRows(datedSampleRows, filters)
    assert.equal(rows.length, 1)
    assert.equal(rows[0].case_code, 'IC-2026-001')
  })

  it('includes older cases when preset is all', () => {
    const rows = filterPipelineRows(datedSampleRows, { ...defaultPipelineFilters(), openedPreset: 'all' })
    assert.equal(rows.length, 2)
  })
})

describe('countActivePipelineFilters date defaults', () => {
  it('does not count default month range as active', () => {
    assert.equal(countActivePipelineFilters(defaultPipelineFilters()), 0)
  })

  it('counts custom range when dates differ from default', () => {
    const n = countActivePipelineFilters({
      ...defaultPipelineFilters(),
      dateFrom: '2026-01-01',
      dateTo: '2026-01-31',
    })
    assert.equal(n, 1)
  })
})

describe('buildPipelineActions', () => {
  it('does not include close action', () => {
    const actions = buildPipelineActions(
      { id: 1, pipeline_column: 'active', product_module: 'homecare' },
      { canAssign: true, canUpdate: true, canCreate: true, canWrite: true },
    )
    assert.ok(!actions.some((a) => a.id === 'close'))
    assert.ok(actions.some((a) => a.id === 'case'))
  })
})
