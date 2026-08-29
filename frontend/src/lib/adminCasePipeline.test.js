import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  buildPipelineActions,
  countActivePipelineFilters,
  defaultOpenedRange,
  defaultPipelineFilters,
  filterPipelineRows,
} from './adminCasePipeline.js'

const sampleRows = [
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
    const rows = filterPipelineRows(sampleRows, filters)
    assert.equal(rows.length, 1)
    assert.equal(rows[0].case_code, 'IC-2026-001')
  })

  it('includes older cases when preset is all', () => {
    const rows = filterPipelineRows(sampleRows, { ...defaultPipelineFilters(), openedPreset: 'all' })
    assert.equal(rows.length, 2)
  })
})

describe('countActivePipelineFilters', () => {
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
