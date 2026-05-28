import { useEffect, useMemo, useState } from 'react'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { sortSupportHistoryByUrgency, isUrgent } from './supportHistoryPriority.js'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminPageHeader,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  AdminToolbar,
  ServiceFilterSelect,
  StatusBadge,
} from './ui/index.js'

function recordTypeLabel(value) {
  if (value === 'tickets') return 'Tickets only'
  if (value === 'incidents') return 'Incidents only'
  return 'All types'
}

function statusLabel(value) {
  if (!value) return null
  const labels = {
    OPEN: 'Open',
    IN_PROGRESS: 'In progress',
    RESOLVED: 'Resolved',
    CLOSED: 'Closed',
    REPORTED: 'Reported',
    IN_REVIEW: 'In review',
    ACTION_TAKEN: 'Action taken',
    ESCALATED: 'Escalated',
  }
  return labels[value] || value
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

export function AdminSupportReportsPage({ embedded = false }) {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [cases, setCases] = useState([])
  const [therapists, setTherapists] = useState([])
  const [search, setSearch] = useState('')

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

  const activeChips = useMemo(
    () =>
      [
        recordType !== 'all' ? recordTypeLabel(recordType) : null,
        statusLabel(status),
        moduleFilter || null,
        dateFrom ? `From ${dateFrom}` : null,
        dateTo ? `To ${dateTo}` : null,
        therapistId ? therapists.find((t) => String(t.id) === therapistId)?.full_name : null,
        childId ? childOptions.find((c) => String(c.id) === childId)?.name : null,
        search ? `Search: ${search}` : null,
      ].filter(Boolean),
    [recordType, status, moduleFilter, dateFrom, dateTo, therapistId, childId, search, therapists, childOptions],
  )

  const sortedRows = useMemo(() => sortSupportHistoryByUrgency(rows), [rows])
  const visibleRows = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return sortedRows
    return sortedRows.filter((r) =>
      [r.subject, r.code, r.client_name, r.therapist_name, r.reporter_name, r.assignee_name]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(q),
    )
  }, [sortedRows, search])

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

  const filterForm = (
    <div className="client-inv__filters client-inv__filters--grid">
      <label className="client-inv__filter-field">
        <span className="client-inv__filter-label">Type</span>
        <select className="admin-input" value={recordType} onChange={(e) => setRecordType(e.target.value)}>
          <option value="all">All types</option>
          <option value="tickets">Tickets only</option>
          <option value="incidents">Incidents only</option>
        </select>
      </label>
      <label className="client-inv__filter-field">
        <span className="client-inv__filter-label">Status</span>
        <select className="admin-input" value={status} onChange={(e) => setStatus(e.target.value)}>
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
      </label>
      <label className="client-inv__filter-field">
        <span className="client-inv__filter-label">Service</span>
        <ServiceFilterSelect className="admin-input" value={moduleFilter} onChange={setModuleFilter} />
      </label>
      <label className="client-inv__filter-field">
        <span className="client-inv__filter-label">From</span>
        <input className="admin-input" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
      </label>
      <label className="client-inv__filter-field">
        <span className="client-inv__filter-label">To</span>
        <input className="admin-input" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
      </label>
      <label className="client-inv__filter-field">
        <span className="client-inv__filter-label">Therapist</span>
        <select className="admin-input" value={therapistId} onChange={(e) => setTherapistId(e.target.value)}>
          <option value="">Any therapist</option>
          {therapists.map((t) => (
            <option key={t.id} value={t.id}>
              {t.full_name}
            </option>
          ))}
        </select>
      </label>
      <label className="client-inv__filter-field">
        <span className="client-inv__filter-label">Client</span>
        <select className="admin-input" value={childId} onChange={(e) => setChildId(e.target.value)}>
          <option value="">Any client</option>
          {childOptions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={load}>
        Apply filters
      </button>
    </div>
  )

  return (
    <div className={embedded ? 'admin-hub-embedded' : 'admin-page'}>
      {!embedded ? (
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
      ) : null}

      <AdminPanel
        title={`${total} records`}
        padded={false}
        actions={
          embedded ? (
            <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={exportCsv}>
              Export CSV
            </button>
          ) : null
        }
      >
        <div className="admin-panel__body">
          <div className="admin-mobile-only">
            <AdminCollapsibleFilters
              filtersOnly
              quickSearch={
                <AdminSearchInput
                  value={search}
                  onChange={setSearch}
                  placeholder="Search code, subject, client…"
                />
              }
              activeChips={activeChips}
              activeCount={activeChips.length}
            >
              {filterForm}
            </AdminCollapsibleFilters>
          </div>
          <div className="admin-desktop-only">
            <AdminToolbar>
              <AdminSearchInput value={search} onChange={setSearch} placeholder="Search code, subject, client…" />
            </AdminToolbar>
            {filterForm}
          </div>

          {loading ? (
            <div className="admin-skeleton" />
          ) : visibleRows.length === 0 ? (
            <AdminEmptyState
              title="No records"
              hints={['Widen the date range', 'Clear status or service filters', 'Try All types']}
            />
          ) : (
            <AdminDataList
              desktop={
                <div className="admin-table-wrap">
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
                      {visibleRows.map((r) => (
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
                          <td>{formatDate(r.created_at)}</td>
                          <td>{formatDate(r.closed_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              }
              mobile={
                <ul className="admin-data-list__cards">
                  {visibleRows.map((r) => (
                    <li key={`${r.record_type}-${r.id}`}>
                      <AdminTaskCard
                        highlight={isUrgent(r)}
                        title={r.subject}
                        meta={
                          <>
                            <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{r.code}</span>
                            {' · '}
                            {r.record_type === 'incident' ? 'Incident' : 'Ticket'}
                            {r.client_name ? ` · ${r.client_name}` : ''}
                          </>
                        }
                        badges={<StatusBadge status={r.status} />}
                      >
                        <p className="admin-muted" style={{ margin: 0, fontSize: '0.8125rem' }}>
                          {r.therapist_name ? `Therapist: ${r.therapist_name}` : 'No therapist on case'}
                          {r.assignee_name ? ` · Assignee: ${r.assignee_name}` : ''}
                        </p>
                        <p className="admin-muted" style={{ margin: '4px 0 0', fontSize: '0.8125rem' }}>
                          Created {formatDate(r.created_at)}
                          {r.priority ? ` · Priority ${r.priority}` : ''}
                          {r.product_module ? ` · ${String(r.product_module).replace(/_/g, ' ')}` : ''}
                        </p>
                      </AdminTaskCard>
                    </li>
                  ))}
                </ul>
              }
            />
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
