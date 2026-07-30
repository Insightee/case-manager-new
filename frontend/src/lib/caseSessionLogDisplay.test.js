import assert from 'node:assert/strict'
import test from 'node:test'
import {
  formatCaseSessionLogCardMeta,
  formatCaseSessionLogCardTitle,
} from './caseSessionLogDisplay.js'

test('formatCaseSessionLogCardTitle uses friendly date and clock', () => {
  const title = formatCaseSessionLogCardTitle(
    {
      scheduled_date: '2026-07-16',
      actual_start_at: '2026-07-16T13:06:00Z',
      actual_end_at: '2026-07-16T13:07:00Z',
    },
    null,
  )
  assert.match(title, /16-07-2026/)
  assert.match(title, /6:36 pm/)
})

test('formatCaseSessionLogCardMeta prioritizes session and log ids', () => {
  const meta = formatCaseSessionLogCardMeta(
    { id: 9225, therapist_user_id: 70 },
    { id: 4032, comment_count: 2 },
  )
  assert.match(meta, /Session #9225/)
  assert.match(meta, /Therapist #70/)
  assert.match(meta, /Log #4032/)
  assert.match(meta, /2 comments/)
})

test('formatCaseSessionLogCardMeta works for orphan logs', () => {
  const meta = formatCaseSessionLogCardMeta(null, {
    id: 4032,
    session_id: 9225,
    scheduled_date: '2026-07-16',
  })
  assert.match(meta, /Session #9225/)
  assert.match(meta, /Log #4032/)
})
