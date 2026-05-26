import { useEffect, useMemo, useState } from 'react'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import {
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  ServiceFilterSelect,
} from './ui/index.js'

export function AdminSupportReportsPage() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [cases, setCases] = useState([])
  const [therapists, setTherapists] = useState([])

  const [recordType, setRecordType] = useState('all')
  const [status, setStatus] = useState('')
  const [moduleFilter, setModuleFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [therapistId, setTherapistId] = useState('')
  const [childId, setChildId] = useState('')

  const childOptions = useMemo(() => {
    const seen = new Map()
    for (const c of cases) {
      if (c.child_id && c.child_name && !seen.has(c.child_id)) {
        seen.set(c.child_id, c.child_name)
      }
    }
    return [...seen.entries()].map(([id, name]) => ({ id, name }))
  }, [cases])

  async function load() {
    setLoading(true)
    try {
      const qs = new URLSearchParams({ record_type: recordType, page_size: '100' })
      if (status) qs.set('status', status)
      if (moduleFilter) qs.set('product_module', moduleFilter)
      if (dateFrom) qs.set('date_from', dateFrom)
      if (dateTo) qs.set('date_to', dateTo)
      if (therapistId) qs.set('therapist_user_id', therapistId)
      if (childId) qs.set('child_id', childId)
      const data = await apiFetch(`/api/v1/admin/support/history?${qs.toString()}`)
      setRows(data.items || [])
      setTotal(data.total ?? 0)
    } catch {
      setRows([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    apiFetch('/api/v1/cases?page_size=200')
      .then((d) => setCases(unwrapList(d)))
      .catch(() => setCases([]))
    apiFetch('/api/v1/admin/users?page_size=100')
      .then((users) => {
        const list = unwrapList(users)
        setTherapists(list.filter((u) => u.roles?.includes('THERAPIST')))
      })
      .catch(() => setTherapists([]))
  }, [])

  function exportCsv() {
    const qs = new URLSearchParams({ record_type: recordType })
    if (status) qs.set('status', status)
    if (moduleFilter) qs.set('product_module', moduleFilter)
    if (dateFrom) qs.set('date_from', dateFrom)
    if (dateTo) qs.set('date_to', dateTo)
    if (therapistId) qs.set('therapist_user_id', therapistId)
    if (childId) qs.set('child_id', childId)
    apiDownload(`/api/v1/admin/support/history/export.csv?${qs.toString()}`, 'support-history.csv')
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Support"
        title="Support & incident reports"
        subtitle="History of tickets and incident reports across your scope."
        actions={
          <button type="button" className="admin-btn admin-btn--secondary" onClick={exportCsv}>
            Export CSV
          </button>
        }
      />

      <AdminPanel title={`${total} records`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', minWidth: 120, paddingLeft: 12, backgroundImage: 'none' }}
              value={recordType}
              onChange={(e) => setRecordType(e.target.value)}
            >
              <option value="all">All types</option>
              <option value="tickets">Tickets only</option>
              <option value="incidents">Incidents only</option>
            </select>
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">Any status</option>
              <option value="OPEN">Open (tickets)</option>
              <option value="IN_PROGRESS">In progress</option>
              <option value="RESOLVED">Resolved</option>
              <option value="CLOSED">Closed</option>
              <option value="REPORTED">Reported (incidents)</option>
              <option value="IN_REVIEW">In review</option>
              <option value="ACTION_TAKEN">Action taken</option>
              <option value="ESCALATED">Escalated</option>
            </select>
            <ServiceFilterSelect
              className="admin-search__input"
              style={{ flex: '0 0 auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={moduleFilter}
              onChange={setModuleFilter}
            />
            <input
              type="date"
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', paddingLeft: 12, backgroundImage: 'none' }}
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              aria-label="From date"
            />
            <input
              type="date"
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', paddingLeft: 12, backgroundImage: 'none' }}
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              aria-label="To date"
            />
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={therapistId}
              onChange={(e) => setTherapistId(e.target.value)}
            >
              <option value="">Any therapist</option>
              {therapists.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name}
                </option>
              ))}
            </select>
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={childId}
              onChange={(e) => setChildId(e.target.value)}
            >
              <option value="">Any client</option>
              {childOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={load}>
              Apply filters
            </button>
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" />
          ) : rows.length === 0 ? (
            <AdminEmptyState title="No records" description="Adjust filters or widen the date range." />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="admin-table" style={{ width: '100%', fontSize: '0.8rem' }}>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Code</th>
                    <th>Subject</th>
                    <th>Status</th>
                    <th>Priority</th>
                    <th>Client</th>
                    <th>Therapist</th>
                    <th>Reporter</th>
                    <th>Assignee</th>
                    <th>Module</th>
                    <th>Created</th>
                    <th>Closed</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={`${r.record_type}-${r.id}`}>
                      <td>{r.record_type}</td>
                      <td style={{ fontFamily: 'monospace' }}>{r.code}</td>
                      <td>{r.subject}</td>
                      <td>{r.status}</td>
                      <td>{r.priority || '—'}</td>
                      <td>{r.client_name || '—'}</td>
                      <td>{r.therapist_name || '—'}</td>
                      <td>{r.reporter_name || '—'}</td>
                      <td>{r.assignee_name || '—'}</td>
                      <td>{r.product_module || '—'}</td>
                      <td>{r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}</td>
                      <td>{r.closed_at ? new Date(r.closed_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
