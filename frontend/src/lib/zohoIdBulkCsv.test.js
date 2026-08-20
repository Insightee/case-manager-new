import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { parseCaseZohoIdBulkCsv } from './zohoIdBulkCsv.js'

describe('parseCaseZohoIdBulkCsv', () => {
  it('reads Case Creation Updates headers and skips empty zoho or case', () => {
    const text = `ID,Parent,Email,Zoho Id,Cases
356,Sujatha Albert,suja@example.com,INS-697,IC-2026-HC-097
277,Sameera,sameera@example.com,CUS-00048,—
426,Aishwarya,asha@example.com,,IC-2026-HC-156
219,Sivani,rahul@example.com,CUS-00753,IC-2026-SS-159`

    const rows = parseCaseZohoIdBulkCsv(text)
    assert.equal(rows.length, 4)
    assert.deepEqual(rows[0], { case_code: 'IC-2026-HC-097', zoho_id: 'INS-697' })
    assert.equal(rows[1].case_code, null)
    assert.equal(rows[1].zoho_id, 'CUS-00048')
    assert.equal(rows[2].case_code, 'IC-2026-HC-156')
    assert.equal(rows[2].zoho_id, null)
    assert.deepEqual(rows[3], { case_code: 'IC-2026-SS-159', zoho_id: 'CUS-00753' })
  })

  it('reads Export records columns', () => {
    const text = `Case Id,Zoho id,Client name
IC-2026-SS-010,INS-547,Asha`
    const rows = parseCaseZohoIdBulkCsv(text)
    assert.deepEqual(rows, [{ case_code: 'IC-2026-SS-010', zoho_id: 'INS-547' }])
  })

  it('infers cells when headers are missing', () => {
    const text = `356\tSujatha Albert\tsuja@example.com\tINS-697\tIC-2026-HC-097`
    const rows = parseCaseZohoIdBulkCsv(text)
    assert.deepEqual(rows, [{ case_code: 'IC-2026-HC-097', zoho_id: 'INS-697' }])
  })
})
