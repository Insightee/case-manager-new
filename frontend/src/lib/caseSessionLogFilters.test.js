import assert from 'node:assert/strict'
import test from 'node:test'
import {
  filterCaseSessionRows,
  matchesCaseSessionLogStatus,
  matchesCaseSessionLogView,
} from './caseSessionLogFilters.js'

test('matchesCaseSessionLogView filters by month and day', () => {
  assert.equal(matchesCaseSessionLogView('2026-07-15', 'month', '2026-07-01', '2026-07'), true)
  assert.equal(matchesCaseSessionLogView('2026-06-30', 'month', '2026-07-01', '2026-07'), false)
  assert.equal(matchesCaseSessionLogView('2026-07-15', 'day', '2026-07-15', '2026-07'), true)
  assert.equal(matchesCaseSessionLogView('2026-07-15', 'all', '2026-07-01', '2026-07'), true)
})

test('matchesCaseSessionLogStatus covers workflow buckets', () => {
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'COMPLETED' }, { approval_status: 'APPROVED' }, 'approved', false),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'SCHEDULED' }, null, 'ongoing', false),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'IN_PROGRESS' }, null, 'ongoing', false),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'COMPLETED' }, null, 'no_log', false),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus(
      { status: 'COMPLETED' },
      { approval_status: 'PENDING', resubmitted_at: '2026-07-01T10:00:00Z' },
      'resubmitted',
      false,
    ),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'COMPLETED' }, { approval_status: 'APPROVED' }, 'times_edited', true),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'CLIENT_ABSENT' }, null, 'child_on_leave', false),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'COMPLETED' }, { attendance_status: 'CLIENT_LEAVE' }, 'child_on_leave', false),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'THERAPIST_LEAVE' }, null, 'therapist_on_leave', false),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus(
      { status: 'COMPLETED' },
      { attendance_status: 'THERAPIST_LEAVE' },
      'therapist_on_leave',
      false,
    ),
    true,
  )
  assert.equal(
    matchesCaseSessionLogStatus({ status: 'CLIENT_ABSENT' }, null, 'therapist_on_leave', false),
    false,
  )
})

test('filterCaseSessionRows keeps highlighted session when filters would hide it', () => {
  const sessions = [
    { id: 1, scheduled_date: '2026-07-10', status: 'COMPLETED' },
    { id: 2, scheduled_date: '2026-06-10', status: 'CANCELLED' },
  ]
  const logsBySessionId = new Map([
    [1, { approval_status: 'APPROVED' }],
    [2, { approval_status: 'APPROVED' }],
  ])

  const { filteredSessions } = filterCaseSessionRows({
    sessions,
    logsBySessionId,
    orphanLogs: [],
    viewMode: 'month',
    selectedDate: '2026-07-30',
    selectedMonth: '2026-07',
    statusFilter: 'approved',
    highlightSessionId: '2',
    sessionHasTimeEdit: () => false,
  })

  assert.deepEqual(
    filteredSessions.map((s) => s.id),
    [1, 2],
  )
})
