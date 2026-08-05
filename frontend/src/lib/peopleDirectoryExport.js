import { accountStatusLabel, clientAccountStatus } from './accountStatus.js'
import { moduleAccessSummary } from './rbacDisplay.js'
import { sortClientsAlphabetical, sortStaffAlphabetical, sortTherapists } from './peopleDirectoryList.js'
import { staffDepartmentLabel } from './staffDepartments.js'

export function escapeCsvCell(value) {
  const text = value == null ? '' : String(value)
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`
  }
  return text
}

export function buildCsv(headers, rows) {
  const lines = [headers.map(escapeCsvCell).join(',')]
  for (const row of rows) {
    lines.push(headers.map((header) => escapeCsvCell(row[header])).join(','))
  }
  return lines.join('\n')
}

export function downloadCsv(filename, csvText) {
  const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.click()
  window.URL.revokeObjectURL(url)
}

/** Directory rows with an established account (exclude invite-only client rows). */
export function isEstablishedClientFamily(family) {
  return Boolean(family?.parents?.[0])
}

function formatRoles(roles) {
  return (roles || []).map((role) => String(role).replace(/_/g, ' ')).join(', ') || '—'
}

function formatModuleAccess(user, catalog, grantsFromAssignments) {
  const rows = moduleAccessSummary(user, catalog, grantsFromAssignments)
  if (!rows.length) return '—'
  return rows.map((row) => `${row.label}: ${row.access}`).join('; ')
}

function formatTherapistServices(user, profile) {
  const services = profile?.services_offered || user?.module_assignments || []
  return services.length ? services.join(', ') : '—'
}

function formatClientCases(family) {
  const cases = family.cases?.length
    ? family.cases
    : (family.caseCodes || []).map((caseCode) => ({ caseCode }))
  const codes = cases.map((entry) => entry.caseCode).filter(Boolean)
  return codes.length ? codes.join(', ') : '—'
}

export function staffCsvRows(staff, { catalog = [], grantsFromAssignments, includeAccess = false, staffDepartments = [] } = {}) {
  const sorted = sortStaffAlphabetical(staff || [])
  const headers = includeAccess
    ? ['Name', 'Email', 'Department', 'Role', 'Access', 'Status']
    : ['Name', 'Email', 'Department', 'Role', 'Status']

  const rows = sorted.map((user) => {
    const base = {
      Name: user.full_name || '—',
      Email: user.email || '—',
      Department: staffDepartmentLabel(user.department, staffDepartments) || '—',
      Role: formatRoles(user.roles),
      Status: accountStatusLabel(user),
    }
    if (includeAccess) {
      base.Access = formatModuleAccess(user, catalog, grantsFromAssignments)
    }
    return base
  })

  return { headers, rows }
}

export function therapistCsvRows(therapists, profileByUser) {
  const sorted = sortTherapists(therapists || [], 'id_asc')
  const headers = [
    'Therapist ID',
    'Name',
    'Email',
    'Phone',
    'Profile',
    'Status',
    'Primary CM',
    'Services',
  ]

  const rows = sorted.map((user) => {
    const profile = profileByUser?.get?.(user.id)
    return {
      'Therapist ID': user.external_employee_id || '—',
      Name: user.full_name || '—',
      Email: user.email || '—',
      Phone: user.phone || '—',
      Profile: profile?.status || 'No profile',
      Status: accountStatusLabel(user),
      'Primary CM': profile?.supervisor_name || '—',
      Services: formatTherapistServices(user, profile),
    }
  })

  return { headers, rows }
}

export function clientCsvRows(clients) {
  const established = (clients || []).filter(isEstablishedClientFamily)
  const sorted = sortClientsAlphabetical(established)
  const headers = ['ID', 'Child', 'Parent', 'Email', 'Phone', 'Status', 'Cases']

  const rows = sorted.map((family) => {
    const primary = family.parents?.[0]
    return {
      ID: family.childId ?? '—',
      Child: family.childName || '—',
      Parent: primary?.parentName || '—',
      Email: primary?.parentEmail || '—',
      Phone: primary?.parentPhone || '—',
      Status: clientAccountStatus(family),
      Cases: formatClientCases(family),
    }
  })

  return { headers, rows }
}

export function exportStaffCsv(staff, options = {}) {
  const { headers, rows } = staffCsvRows(staff, options)
  const csv = buildCsv(headers, rows)
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(`people-staff-${date}.csv`, csv)
}

export function exportTherapistCsv(therapists, profileByUser) {
  const { headers, rows } = therapistCsvRows(therapists, profileByUser)
  const csv = buildCsv(headers, rows)
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(`people-therapists-${date}.csv`, csv)
}

export function exportClientCsv(clients) {
  const { headers, rows } = clientCsvRows(clients)
  const csv = buildCsv(headers, rows)
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(`people-clients-${date}.csv`, csv)
}
