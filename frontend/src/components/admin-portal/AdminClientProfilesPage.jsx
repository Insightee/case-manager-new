import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar } from './ui/index.js'

function parseClientCsv(text) {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  if (!lines.length) return []
  const header = lines[0].toLowerCase()
  const dataLines = header.includes('email') || header.includes('child') ? lines.slice(1) : lines
  return dataLines.map((line) => {
    const parts = line.includes('\t') ? line.split('\t') : line.split(',').map((p) => p.trim())
    const [childFirst, childLast, parentEmail, parentName, parentPhone = ''] = parts
    return {
      child_first: childFirst || '',
      child_last: childLast || '',
      parent_email: parentEmail || '',
      parent_full_name: parentName || '',
      parent_phone: parentPhone || null,
    }
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

  function buildBulkRows() {
    return parseClientCsv(bulkText).filter((r) => r.parent_email && r.child_first)
  }

  function goBulkPreview(e) {
    e?.preventDefault()
    const rows = buildBulkRows()
    if (!rows.length) {
      setError('Add at least one row: child first, child last, parent email, parent name, phone (optional)')
      return
    }
    setError('')
    setSuccess('')
    setBulkResults(null)
    setBulkPreview(rows)
    setBulkPhase('preview')
  }

  async function confirmBulkImport() {
    const rows = bulkPreview || buildBulkRows()
    if (!rows.length) return
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

  function resetBulkImport() {
    setBulkPhase('edit')
    setBulkPreview(null)
    setBulkResults(null)
    setBulkText('')
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
        <AdminPanel title="Bulk client import" subtitle="CSV columns: child first, child last, parent email, parent name, phone (optional)">
          {bulkPhase === 'edit' ? (
            <form onSubmit={goBulkPreview}>
              <textarea
                className="admin-input"
                rows={6}
                placeholder="Asha, Kumar, parent@example.com, Priya Kumar, +91 98765 43210"
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.85rem' }}
              />
              <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" style={{ marginTop: 8 }}>
                Preview rows
              </button>
            </form>
          ) : null}

          {bulkPhase === 'preview' && bulkPreview?.length ? (
            <>
              {duplicatePreviewIndexes.size ? (
                <p className="admin-alert" style={{ marginBottom: 12 }}>
                  Duplicate rows in file (same parent email and child name). Only the first of each duplicate will import; later duplicates will fail.
                </p>
              ) : null}
              <div className="admin-table-wrap">
                <table className="admin-table" style={{ marginBottom: 16 }}>
                  <thead>
                    <tr>
                      <th>Child first</th>
                      <th>Child last</th>
                      <th>Parent email</th>
                      <th>Parent name</th>
                      <th>Phone</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bulkPreview.map((r, idx) => (
                      <tr key={`${clientRowKey(r)}-${idx}`} style={duplicatePreviewIndexes.has(idx) ? { opacity: 0.65 } : undefined}>
                        <td>{r.child_first}</td>
                        <td>{r.child_last || '—'}</td>
                        <td>{r.parent_email}</td>
                        <td>{r.parent_full_name || '—'}</td>
                        <td>{r.parent_phone || '—'}</td>
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
