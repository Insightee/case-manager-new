import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildCaseSessionLogExportQuery,
  caseSessionLogExportFilename,
  caseSessionLogExportPath,
  caseSessionLogExportPeriodLabel,
} from './sessionLogBulkExport.js'

test('builds staff export query with summary defaults', () => {
  const query = buildCaseSessionLogExportQuery({
    viewMode: 'month',
    selectedMonth: '2026-03',
    statusFilter: 'approved',
    includeContent: false,
  })
  assert.equal(query, 'view_mode=month&month=2026-03&status=approved')
})

test('builds parent export path and filename', () => {
  const query = buildCaseSessionLogExportQuery({
    viewMode: 'day',
    selectedDate: '2026-03-15',
    attendanceFilter: 'COMPLETED',
    includeContent: true,
  })
  assert.equal(
    caseSessionLogExportPath(42, { parent: true, query }),
    '/api/v1/parent/session-logs/export/xlsx?case_id=42&view_mode=day&date=2026-03-15&attendance=COMPLETED&include_content=true',
  )
  assert.equal(
    caseSessionLogExportFilename({ caseCode: 'IC-001', periodLabel: '2026-03-15' }),
    'session_logs_IC-001_2026-03-15.xlsx',
  )
})

test('derives period label from filters', () => {
  assert.equal(caseSessionLogExportPeriodLabel({ viewMode: 'month', selectedMonth: '2026-04' }), '2026-04')
  assert.equal(caseSessionLogExportPeriodLabel({ viewMode: 'all', year: '2025' }), '2025')
})
