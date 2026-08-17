import assert from 'node:assert/strict'
import test from 'node:test'
import {
  canDownloadApprovedSessionLog,
  sessionLogDownloadFilename,
  sessionLogDownloadPath,
} from './sessionLogDownload.js'

test('canDownloadApprovedSessionLog is true only for approved real logs', () => {
  assert.equal(canDownloadApprovedSessionLog({ id: 12, approval_status: 'APPROVED' }), true)
  assert.equal(canDownloadApprovedSessionLog({ id: 12, parent_display_status: 'Reviewed' }), true)
  assert.equal(canDownloadApprovedSessionLog({ id: 12, approval_status: 'PENDING' }), false)
  assert.equal(canDownloadApprovedSessionLog({ id: 12, parent_display_status: 'Under Review' }), false)
  assert.equal(canDownloadApprovedSessionLog({ id: -4, approval_status: 'APPROVED' }), false)
  assert.equal(canDownloadApprovedSessionLog(null), false)
})

test('sessionLogDownloadPath uses parent or staff routes', () => {
  assert.equal(sessionLogDownloadPath(9), '/api/v1/daily-logs/9/download')
  assert.equal(sessionLogDownloadPath(9, { parent: true }), '/api/v1/parent/session-logs/9/download')
})

test('sessionLogDownloadFilename sanitizes case code and date', () => {
  assert.equal(
    sessionLogDownloadFilename({ id: 3, case_code: 'HC-12', scheduled_date: '2026-08-14' }),
    'session_log_HC-12_2026-08-14.pdf',
  )
})
