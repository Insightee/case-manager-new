import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  INFO_ACCESS,
  WEBHOOK_EVENTS,
  emptyKeyDraft,
  keyPayloadFromDraft,
  parseCaseIds,
  caseIdsToText,
  filterGrantCases,
  toggleGrantedCaseId,
  scopesFromDraft,
  validateKeyDraft,
  validateWebhookDraft,
} from './integrationDesk.js'

describe('integrationDesk', () => {
  it('exposes eight information areas and seven webhook events', () => {
    assert.equal(INFO_ACCESS.length, 8)
    assert.equal(WEBHOOK_EVENTS.length, 7)
    assert.deepEqual(
      INFO_ACCESS.map((item) => item.id),
      ['cases', 'sessions', 'reports', 'goals', 'iep', 'reporting', 'ops', 'profiles'],
    )
  })

  it('builds read scopes and keeps reports, IEP, reporting, and ops read-only', () => {
    const draft = {
      ...emptyKeyDraft(),
      allowRead: true,
      allowWrite: true,
      infoAccess: INFO_ACCESS.map((item) => item.id),
    }
    const scopes = scopesFromDraft(draft)
    assert.ok(scopes.includes('cases:read'))
    assert.ok(scopes.includes('cases:write'))
    assert.ok(scopes.includes('sessions:summarize'))
    assert.ok(scopes.includes('goals:write'))
    assert.ok(scopes.includes('profiles:read'))
    assert.ok(scopes.includes('profiles:write'))
    assert.equal(scopes.includes('reports:write'), false)
    assert.equal(scopes.includes('iep:write'), false)
    assert.equal(scopes.includes('ops:write'), false)
    assert.ok(scopes.includes('reports:read'))
  })

  it('asks for read or write and at least one information area', () => {
    const draft = { ...emptyKeyDraft(), name: 'Partner', allowRead: false, allowWrite: false }
    assert.match(validateKeyDraft(draft), /Read or Write/)
    const noInfo = { ...emptyKeyDraft(), name: 'Partner', infoAccess: [] }
    assert.match(validateKeyDraft(noInfo), /at least one kind of information/)
  })

  it('parses case ids and rejects words', () => {
    assert.deepEqual(parseCaseIds('12, 48 48'), { ids: [12, 48], error: '' })
    assert.match(parseCaseIds('12, abc').error, /numbers/)
  })

  it('filters grant cases by status and search, and toggles ids', () => {
    const rows = [
      { id: 1, case_code: 'HC-1', child_name: 'Aarav', status: 'ACTIVE', therapist_name: 'Neha' },
      { id: 2, case_code: 'SS-2', child_name: 'Diya', status: 'CLOSED', therapist_name: 'Neha' },
      { id: 3, case_code: 'HC-3', child_name: 'Kabir', status: 'SUSPENDED', case_manager_name: 'Priya' },
    ]
    assert.deepEqual(filterGrantCases(rows, { status: 'ACTIVE' }).map((row) => row.id), [1])
    assert.deepEqual(filterGrantCases(rows, { query: 'priya' }).map((row) => row.id), [3])
    assert.deepEqual(toggleGrantedCaseId([1], 2), [1, 2])
    assert.deepEqual(toggleGrantedCaseId([1, 2], 1), [2])
    assert.equal(caseIdsToText([2, 1, 1]), '2, 1')
  })

  it('sends structured flags instead of free-text scopes', () => {
    const payload = keyPayloadFromDraft({
      ...emptyKeyDraft(),
      name: '  School agent  ',
      caseIdsText: '3, 9',
      allowWrite: true,
    })
    assert.equal(payload.name, 'School agent')
    assert.deepEqual(payload.case_ids, [3, 9])
    assert.equal(payload.allow_read, true)
    assert.equal(payload.allow_write, true)
    assert.equal(payload.mcp_enabled, true)
    assert.ok(!('scopes' in payload))
  })

  it('requires https for webhooks', () => {
    assert.match(
      validateWebhookDraft({ integrationClientId: '1', url: 'http://example.com/hook', events: ['session.logged'] }),
      /https/,
    )
    assert.equal(
      validateWebhookDraft({
        integrationClientId: '1',
        url: 'https://example.com/hook',
        events: ['session.logged'],
      }),
      '',
    )
  })
})
