import { describe, expect, it } from 'vitest'
import {
  buildCsv,
  clientCsvRows,
  escapeCsvCell,
  isEstablishedClientFamily,
  staffCsvRows,
  therapistCsvRows,
} from './peopleDirectoryExport.js'

describe('peopleDirectoryExport', () => {
  it('escapes csv cells with commas and quotes', () => {
    expect(escapeCsvCell('plain')).toBe('plain')
    expect(escapeCsvCell('a,b')).toBe('"a,b"')
    expect(escapeCsvCell('say "hi"')).toBe('"say ""hi"""')
  })

  it('builds csv with headers', () => {
    const csv = buildCsv(['Name', 'Email'], [{ Name: 'Ada', Email: 'ada@demo.com' }])
    expect(csv).toBe('Name,Email\nAda,ada@demo.com')
  })

  it('exports staff rows with access when requested', () => {
    const { headers, rows } = staffCsvRows(
      [{ full_name: 'Case Manager', email: 'cm@demo.com', roles: ['CASE_MANAGER'], is_active: true, login_ready: true }],
      { includeAccess: true, catalog: [], grantsFromAssignments: () => ({}) },
    )
    expect(headers).toContain('Access')
    expect(rows[0].Name).toBe('Case Manager')
    expect(rows[0].Status).toBe('Active')
  })

  it('exports therapist rows with profile fields', () => {
    const profileByUser = new Map([
      [
        2,
        {
          status: 'ACTIVE',
          supervisor_name: 'Lead CM',
          services_offered: ['homecare'],
        },
      ],
    ])
    const { rows } = therapistCsvRows(
      [{ id: 2, external_employee_id: 'T-01', full_name: 'Therapist', email: 't@demo.com', is_active: true, login_ready: true }],
      profileByUser,
    )
    expect(rows[0]['Therapist ID']).toBe('T-01')
    expect(rows[0]['Primary CM']).toBe('Lead CM')
    expect(rows[0].Services).toBe('homecare')
  })

  it('skips invite-only client families', () => {
    expect(isEstablishedClientFamily({ parents: [] })).toBe(false)
    expect(isEstablishedClientFamily({ parents: [{ parentName: 'Parent' }] })).toBe(true)

    const { rows } = clientCsvRows([
      { childId: 1, childName: 'Child A', parents: [{ parentName: 'Parent', parentEmail: 'p@demo.com' }], cases: [] },
      { childId: 2, childName: 'Pending', parents: [], pendingInvite: { pendingEmail: 'new@demo.com' } },
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0].Child).toBe('Child A')
  })
})
