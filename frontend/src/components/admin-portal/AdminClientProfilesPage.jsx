import { useCallback, useEffect, useState } from 'react'
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

export function AdminClientProfilesPage() {
  const navigate = useNavigate()
  const { can } = useAuth()
  const [families, setFamilies] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [bulkText, setBulkText] = useState('')
  const [importing, setImporting] = useState(false)

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

  async function runBulkImport(e) {
    e.preventDefault()
    const rows = parseClientCsv(bulkText).filter((r) => r.parent_email && r.child_first)
    if (!rows.length) {
      setError('Add at least one row: child first, child last, parent email, parent name, phone')
      return
    }
    setImporting(true)
    setError('')
    setSuccess('')
    try {
      const res = await apiFetch('/api/v1/admin/clients/bulk-import', {
        method: 'POST',
        body: JSON.stringify({ rows }),
      })
      setSuccess(`Imported ${res.success_count} of ${res.total} families`)
      setBulkText('')
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
        <AdminPanel title="Bulk client import" subtitle="CSV columns: child first, child last, parent email, parent name, phone (optional)">
          <form onSubmit={runBulkImport}>
            <textarea
              className="admin-input"
              rows={6}
              placeholder="Asha, Kumar, parent@example.com, Priya Kumar, +91 98765 43210"
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.85rem' }}
            />
            <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" style={{ marginTop: 8 }} disabled={importing}>
              {importing ? 'Importing…' : 'Import families'}
            </button>
          </form>
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
