import assert from 'node:assert/strict'
import test from 'node:test'

import { resolveNotificationLinkAsync } from './notificationLinks.js'


test('billing approval notification opens the exact case billing request', async () => {
  const apiFetch = async (path) => {
    assert.equal(path, '/api/v1/billing-approvals/42')
    return { caseId: 7 }
  }

  const link = await resolveNotificationLinkAsync(
    'billing_approval_request',
    42,
    'admin',
    apiFetch,
  )

  assert.equal(link, '/admin/cases/7?tab=billing&billing_approval=42')
})
