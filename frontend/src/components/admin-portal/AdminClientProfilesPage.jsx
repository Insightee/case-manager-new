import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar } from './ui/index.js'

function parseCsv(text) {
  const lines = []
  const pattern = /("([^"]*(?:""[^"]*)*)"|([^",\r\n]*))/gi
  
  const textLines = text.split(/\r?\n/)
  for (const line of textLines) {
    if (!line.trim()) continue
    const row = []
    pattern.lastIndex = 0
    let match
    while ((match = pattern.exec(line)) !== null) {
      if (match.index === pattern.lastIndex) {
        pattern.lastIndex++
      }
      const rawValue = match[2] !== undefined ? match[2] : match[3]
      const cleanValue = rawValue ? rawValue.replace(/""/g, '"').trim() : ''
      row.push(cleanValue)
    }
    if (row.length > 0) {
      if (line.endsWith(',') === false && row[row.length - 1] === '') {
        row.pop()
      }
      lines.push(row)
    }
  }
  return lines
}

function parseClientCsv(text) {
  const rawRows = parseCsv(text)
  if (!rawRows.length) return []
  const headers = rawRows[0].map(h => h.toLowerCase().trim())
  
  const fields = {
    child_first: ['child_first_name', 'child_first', 'child first name', 'child first'],
    child_last: ['child_last_name', 'child_last', 'child last name', 'child last'],
    parent_email: ['parent_email', 'parent email', 'email'],
    parent_full_name: ['parent_full_name', 'parent_full', 'parent name', 'parent full name'],
    parent_phone: ['parent_phone', 'parent phone', 'phone'],
    case_reference: ['case_reference', 'case reference', 'case_code', 'case code'],
    product_module: ['product_module', 'product module', 'module'],
    service_type: ['service_type', 'service type', 'service_location_type', 'service location type'],
    service_address_line1: ['service_address_line1', 'service address line 1', 'address line 1'],
    service_address_line2: ['service_address_line2', 'service address line 2', 'address line 2'],
    service_city: ['service_city', 'service city', 'city'],
    service_state: ['service_state', 'service state', 'state'],
    service_pincode: ['service_pincode', 'service pincode', 'pincode', 'postal code'],
    service_landmark: ['service_landmark', 'service landmark', 'landmark'],
    billing_address_same_as_service: ['billing_address_same_as_service', 'billing address same as service'],
    billing_address_line1: ['billing_address_line1', 'billing address line 1'],
    billing_address_line2: ['billing_address_line2', 'billing address line 2'],
    billing_address_city: ['billing_address_city', 'billing address city'],
    billing_address_state: ['billing_address_state', 'billing address state'],
    billing_address_pincode: ['billing_address_pincode', 'billing address pincode'],
    billing_address_landmark: ['billing_address_landmark', 'billing address landmark'],
    billing_type: ['billing_type', 'billing type'],
    client_billing_mode: ['client_billing_mode', 'client billing mode'],
    client_rate_per_session_inr: ['client_rate_per_session_inr', 'client rate per session inr', 'client rate', 'rate'],
    package_session_count: ['package_session_count', 'package session count'],
    package_amount_inr: ['package_amount_inr', 'package amount inr', 'package amount'],
    compensation_mode: ['compensation_mode', 'compensation mode'],
    pay_share_amount_inr: ['pay_share_amount_inr', 'pay share amount inr', 'therapist pay share', 'pay share'],
    therapist_fixed_pay_inr: ['therapist_fixed_pay_inr', 'therapist fixed pay inr'],
    billing_notes: ['billing_notes', 'billing notes'],
    therapist_email: ['therapist_email', 'therapist email']
  }

  const headerIndices = {}
  for (const [field, aliases] of Object.entries(fields)) {
    const idx = headers.findIndex(h => aliases.includes(h))
    if (idx !== -1) {
      headerIndices[field] = idx
    }
  }

  const dataRows = rawRows.slice(1)
  return dataRows.map(row => {
    const obj = {}
    for (const [field, idx] of Object.entries(headerIndices)) {
      obj[field] = row[idx] !== undefined ? row[idx].trim() : ''
    }
    
    // Normalize boolean
    if (obj.billing_address_same_as_service) {
      const val = obj.billing_address_same_as_service.toLowerCase()
      obj.billing_address_same_as_service = val === 'true' || val === 'yes' || val === 'y' || val === '1'
    } else {
      obj.billing_address_same_as_service = true
    }

    if (obj.client_rate_per_session_inr) {
      obj.client_rate_per_session_inr = parseFloat(obj.client_rate_per_session_inr) || null
    }
    if (obj.package_session_count) {
      obj.package_session_count = parseInt(obj.package_session_count, 10) || null
    }
    if (obj.package_amount_inr) {
      obj.package_amount_inr = parseFloat(obj.package_amount_inr) || null
    }
    if (obj.pay_share_amount_inr) {
      obj.pay_share_amount_inr = parseFloat(obj.pay_share_amount_inr) || null
    }
    if (obj.therapist_fixed_pay_inr) {
      obj.therapist_fixed_pay_inr = parseFloat(obj.therapist_fixed_pay_inr) || null
    }

    if (!obj.child_first) {
      obj.child_first = row[0] || ''
    }
    if (!obj.parent_email) {
      obj.parent_email = row[2] || ''
    }

    return obj
  })
}

function clientRowKey(row) {
  return [
    (row.parent_email || '').trim().toLowerCase(),
    (row.child_first || '').trim().toLowerCase(),
    (row.child_last || '').trim().toLowerCase(),
  ].join('|')
}

function findDuplicateRowIndexes(rows) {
  const seen = new Map()
  const dupes = new Set()
  rows.forEach((row, idx) => {
    if (!row.parent_email?.trim() || !row.child_first?.trim()) return
    const key = clientRowKey(row)
    if (seen.has(key)) {
      dupes.add(idx)
      dupes.add(seen.get(key))
    } else {
      seen.set(key, idx)
    }
  })
  return dupes
}

function buildImportSummary(res) {
  const parts = []
  if (res.invited_count) {
    parts.push(`${res.invited_count} new ${res.invited_count === 1 ? 'family' : 'families'} invited`)
  }
  if (res.linked_existing_parent_count) {
    parts.push(
      `${res.linked_existing_parent_count} ${res.linked_existing_parent_count === 1 ? 'child' : 'children'} added to existing parent${res.linked_existing_parent_count === 1 ? '' : 's'}`,
    )
  }
  if (res.failed_count) {
    parts.push(`${res.failed_count} failed`)
  }
  if (!parts.length) return 'No rows imported'
  return parts.join(' · ')
}

function outcomeLabel(outcome) {
  if (outcome === 'invited') return 'Invited'
  if (outcome === 'linked_existing_parent') return 'Added to existing parent'
  return 'Failed'
}

function downloadCsvTemplate() {
  const headers = [
    'child_first_name',
    'child_last_name',
    'parent_email',
    'parent_full_name',
    'parent_phone',
    'case_reference',
    'product_module',
    'service_type',
    'service_address_line1',
    'service_address_line2',
    'service_city',
    'service_state',
    'service_pincode',
    'service_landmark',
    'billing_address_same_as_service',
    'billing_address_line1',
    'billing_address_line2',
    'billing_address_city',
    'billing_address_state',
    'billing_address_pincode',
    'billing_address_landmark',
    'billing_type',
    'client_billing_mode',
    'client_rate_per_session_inr',
    'package_session_count',
    'package_amount_inr',
    'compensation_mode',
    'pay_share_amount_inr',
    'therapist_fixed_pay_inr',
    'billing_notes',
    'therapist_email'
  ];
  const row = [
    'Aarav',
    'M.',
    'parent@demo.com',
    'Parent Guardian',
    '+91 9999999999',
    'IC-2026-041',
    'homecare',
    'Home',
    '123 Main Street',
    'Apt 4B',
    'Bangalore',
    'Karnataka',
    '560001',
    'Near Metro Station',
    'true',
    '',
    '',
    '',
    '',
    '',
    '',
    'PER_SESSION',
    'POSTPAID',
    '1000',
    '',
    '',
    'FIXED_LUMP',
    '600',
    '600',
    'Notes',
    'therapist@demo.com'
  ];
  const csvContent = [headers.join(','), row.join(',')].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', 'client_bulk_import_template.csv');
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function AdminClientProfilesPage() {
  const navigate = useNavigate()
  const { can } = useAuth()
  const [families, setFamilies] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [bulkText, setBulkText] = useState('')
  const [bulkPhase, setBulkPhase] = useState('edit')
  const [bulkPreview, setBulkPreview] = useState(null)
  const [bulkResults, setBulkResults] = useState(null)
  const [importing, setImporting] = useState(false)

  const duplicatePreviewIndexes = useMemo(
    () => (bulkPreview ? findDuplicateRowIndexes(bulkPreview) : new Set()),
    [bulkPreview],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const qs = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''
      const rows = await apiFetch(`/api/v1/admin/families${qs}`)
      setFamilies(Array.isArray(rows) ? rows : [])
    } catch (err) {
      setError(err.message || 'Could not load client profiles')
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => {
    const t = setTimeout(load, 300)
    return () => clearTimeout(t)
  }, [load])

  function resetBulkImport() {
    setBulkPhase('edit')
    setBulkPreview(null)
    setBulkResults(null)
    setBulkText('')
  }

  async function confirmBulkImport() {
    const rows = bulkPreview
    if (!rows || !rows.length) return
    setImporting(true)
    setError('')
    setSuccess('')
    try {
      const res = await apiFetch('/api/v1/admin/clients/bulk-import', {
        method: 'POST',
        body: JSON.stringify({ rows }),
      })
      setBulkResults(res.results || [])
      setBulkPhase('done')
      setSuccess(buildImportSummary(res))
      load()
    } catch (err) {
      setError(err.message || 'Bulk import failed')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="People"
        title="Client profiles"
        subtitle="Family directory, parent linkage, and bulk client intake."
        actions={
          can('case.create') ? (
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              onClick={() => navigate('/admin/cases?allot=1')}
            >
              Add client & case
            </button>
          ) : null
        }
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      {can('user.manage') ? (
        <AdminPanel title="Bulk client import" subtitle="Download template, fill client & case details, and upload the CSV file.">
          {bulkPhase === 'edit' ? (
            <div>
              <div className="admin-btn-group" style={{ marginBottom: 16 }}>
                <button
                  type="button"
                  className="admin-btn admin-btn--secondary admin-btn--sm"
                  onClick={downloadCsvTemplate}
                >
                  Download CSV Template
                </button>
              </div>
              <div
                style={{
                  border: '2px dashed var(--admin-border)',
                  borderRadius: 'var(--admin-radius)',
                  padding: '32px',
                  textAlign: 'center',
                  background: 'var(--admin-bg-alt)',
                  cursor: 'pointer'
                }}
                onClick={() => document.getElementById('csv-file-input').click()}
              >
                <p style={{ margin: 0, fontWeight: 500 }}>Click to select a CSV file or drag and drop here</p>
                <p className="admin-muted" style={{ margin: '8px 0 0', fontSize: '0.85rem' }}>
                  Supported headers: child_first_name, parent_email, product_module, service_address_line1, etc.
                </p>
                <input
                  id="csv-file-input"
                  type="file"
                  accept=".csv"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    const reader = new FileReader()
                    reader.onload = (event) => {
                      const text = event.target?.result
                      if (typeof text === 'string') {
                        setBulkText(text)
                        const rows = parseClientCsv(text).filter((r) => r.parent_email && r.child_first)
                        if (!rows.length) {
                          setError('No valid rows found in CSV. Ensure child_first_name and parent_email are filled.')
                          return
                        }
                        setError('')
                        setSuccess('')
                        setBulkResults(null)
                        setBulkPreview(rows)
                        setBulkPhase('preview')
                      }
                    }
                    reader.readAsText(file)
                  }}
                />
              </div>
            </div>
          ) : null}

          {bulkPhase === 'preview' && bulkPreview?.length ? (
            <>
              {duplicatePreviewIndexes.size ? (
                <p className="admin-alert" style={{ marginBottom: 12 }}>
                  Duplicate rows in file (same parent email and child name).
                </p>
              ) : null}
              <div className="admin-table-wrap">
                <table className="admin-table" style={{ marginBottom: 16 }}>
                  <thead>
                    <tr>
                      <th>Child</th>
                      <th>Parent</th>
                      <th>Case/Address</th>
                      <th>Billing & Rates</th>
                      <th>Therapist Assignment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bulkPreview.map((r, idx) => (
                      <tr key={`${clientRowKey(r)}-${idx}`} style={duplicatePreviewIndexes.has(idx) ? { opacity: 0.65 } : undefined}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{r.child_first} {r.child_last}</div>
                        </td>
                        <td>
                          <div>{r.parent_full_name || '—'}</div>
                          <div className="admin-muted" style={{ fontSize: '0.8rem' }}>{r.parent_email}</div>
                          {r.parent_phone && <div className="admin-muted" style={{ fontSize: '0.8rem' }}>{r.parent_phone}</div>}
                        </td>
                        <td>
                          {r.product_module ? (
                            <>
                              <div><span className="admin-pill admin-pill--sm">{r.product_module}</span> {r.service_type || ''}</div>
                              <div className="admin-muted" style={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
                                {r.service_address_line1 || 'No service address'}
                                {r.service_city ? `, ${r.service_city}` : ''}
                              </div>
                            </>
                          ) : (
                            <span className="admin-muted">—</span>
                          )}
                        </td>
                        <td>
                          {r.billing_type ? (
                            <>
                              <div>{r.billing_type} ({r.client_billing_mode || '—'})</div>
                              <div className="admin-muted" style={{ fontSize: '0.8rem' }}>
                                Client: ₹{r.billing_type === 'PACKAGE' ? r.package_amount_inr : r.client_rate_per_session_inr}
                                {r.billing_type === 'PACKAGE' && ` (${r.package_session_count} sess)`}
                              </div>
                              <div className="admin-muted" style={{ fontSize: '0.8rem' }}>
                                Therapist pay: ₹{r.therapist_fixed_pay_inr || r.pay_share_amount_inr || '—'}
                              </div>
                            </>
                          ) : (
                            <span className="admin-muted">—</span>
                          )}
                        </td>
                        <td>
                          {r.therapist_email ? (
                            <div>{r.therapist_email}</div>
                          ) : (
                            <span className="admin-muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="admin-btn-group">
                <button
                  type="button"
                  className="admin-btn admin-btn--primary admin-btn--sm"
                  disabled={importing}
                  onClick={confirmBulkImport}
                >
                  {importing ? 'Importing…' : `Confirm import (${bulkPreview.length})`}
                </button>
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setBulkPhase('edit')}>
                  Back
                </button>
              </div>
            </>
          ) : null}

          {bulkPhase === 'done' && bulkResults?.length ? (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table" style={{ marginBottom: 16 }}>
                  <thead>
                    <tr>
                      <th>Child</th>
                      <th>Parent email</th>
                      <th>Case Reference</th>
                      <th>Status</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bulkResults.map((r, idx) => (
                      <tr key={`${r.parent_email}-${r.child_first}-${idx}`}>
                        <td>
                          {r.child_first} {r.child_last || ''}
                        </td>
                        <td>{r.parent_email}</td>
                        <td>{r.case_code || '—'}</td>
                        <td>{r.success ? outcomeLabel(r.outcome) : 'Failed'}</td>
                        <td>{r.error || (r.child_id ? `Child #${r.child_id}` : '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={resetBulkImport}>
                Import more
              </button>
            </>
          ) : null}
        </AdminPanel>
      ) : null}

      <AdminToolbar>
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search child or parent…" />
      </AdminToolbar>

      <AdminPanel title={`Families (${families.length})`} padded={false}>
        {loading ? (
          <p className="admin-muted" style={{ padding: 16 }}>Loading…</p>
        ) : families.length === 0 ? (
          <AdminEmptyState title="No clients" description="Use bulk import or case allotment to add families." />
        ) : (
          <ul className="admin-queue" style={{ margin: 0 }}>
            {families.map((f) => (
              <li key={f.childId} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">{f.childName}</p>
                  <p className="admin-queue__meta">
                    {f.parents?.length
                      ? f.parents.map((p) => `${p.parentName} · ${p.parentEmail}`).join(' | ')
                      : f.pendingInvite
                        ? `Invite pending: ${f.pendingInvite.pendingEmail}`
                        : 'No parent linked'}
                  </p>
                  {f.caseCodes?.length ? (
                    <p className="admin-queue__meta">
                      Cases:{' '}
                      {f.caseCodes.map((code) => (
                        <Link key={code} to={`/admin/cases?search=${encodeURIComponent(code)}`}>
                          {code}
                        </Link>
                      ))}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </AdminPanel>
    </div>
  )
}
