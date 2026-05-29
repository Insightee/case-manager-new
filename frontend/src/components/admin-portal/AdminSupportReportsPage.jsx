import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useClinicalProductModules, clinicalProductModuleLabel } from '../../hooks/useClinicalProductModules.js'
import { sortSupportHistoryByUrgency, isUrgent } from './supportHistoryPriority.js'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminFilterGrid,
  AdminPageHeader,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  FilterDateRange,
  FilterSelect,
  StatusBadge,
} from './ui/index.js'
import './admin-reports.css'

const RECORD_TYPE_OPTIONS = [
  { value: 'all', label: 'All types' },
  { value: 'tickets', label: 'Tickets only' },
  { value: 'incidents', label: 'Incidents only' },
]

const STATUS_OPTIONS = [
  { value: '', label: 'Any status' },
  { value: 'OPEN', label: 'Open (tickets)' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'CLOSED', label: 'Closed' },
  { value: 'REPORTED', label: 'Reported (incidents)' },
  { value: 'IN_REVIEW', label: 'In review' },
  { value: 'ACTION_TAKEN', label: 'Action taken' },
  { value: 'ESCALATED', label: 'Escalated' },
]

function recordTypeLabel(value) {
  return RECORD_TYPE_OPTIONS.find((o) => o.value === value)?.label || 'All types'
}

function statusLabel(value) {
  if (!value) return null
  return STATUS_OPTIONS.find((o) => o.value === value)?.label || value
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

function historyRowActions(row) {
  const linkStyle = { color: '#6366f1', fontSize: '0.8125rem' }
  if (row.record_type === 'incident') {
    return (
      <span style={{ whiteSpace: 'nowrap' }}>
        <Link to={`/admin/support?tab=incidents&incident=${row.id}`} style={linkStyle}>
          View report
        </Link>
        {row.case_id ? (
          <>
            <span className="admin-muted"> · </span>
            <Link to={`/admin/cases/${row.case_id}?tab=incidents`} style={linkStyle}>
              View case
            </Link>
          </>
        ) : null}
      </span>
    )
  }
  return (
    <span style={{ whiteSpace: 'nowrap' }}>
      <Link to={`/admin/support?tab=tickets&ticket=${row.id}`} style={linkStyle}>
        View ticket
      </Link>
      {row.case_id ? (
        <>
          <span className="admin-muted"> · </span>
          <Link to={`/admin/cases/${row.case_id}`} style={linkStyle}>
            View case
          </Link>
        </>
      ) : null}
    </span>
  )
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

  const { options: moduleOptions, labelByValue: moduleLabels } = useClinicalProductModules()

  const childOptions = useMemo(() => {
    const seen = new Map()
    for (const c of cases) {
      if (c.child_id && c.child_name && !seen.has(c.child_id)) {
        seen.set(c.child_id, c.child_name)
      }
    }
    return [{ value: '', label: 'Any client' }, ...[...seen.entries()].map(([id, name]) => ({ value: String(id), label: name }))]
  }, [cases])

  const therapistOptions = useMemo(
    () => [
      { value: '', label: 'Any therapist' },
      ...therapists.map((t) => ({ value: String(t.id), label: t.full_name || `Therapist #${t.id}` })),
    ],
    [therapists],
  )

  const activeChips = useMemo(
    () =>
      [
        recordType !== 'all' ? recordTypeLabel(recordType) : null,
        statusLabel(status),
        moduleFilter ? clinicalProductModuleLabel(moduleFilter, moduleLabels) : null,
        dateFrom ? `From ${dateFrom}` : null,
        dateTo ? `To ${dateTo}` : null,
        therapistId ? therapists.find((t) => String(t.id) === therapistId)?.full_name : null,
        childId ? childOptions.find((c) => c.value === childId)?.label : null,
        search ? `Search: ${search}` : null,
      ].filter(Boolean),
    [recordType, status, moduleFilter, dateFrom, dateTo, therapistId, childId, search, therapists, childOptions, moduleLabels],
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

  const kpis = useMemo(() => {
    const tickets = visibleRows.filter((r) => r.record_type === 'ticket').length
    const incidents = visibleRows.filter((r) => r.record_type === 'incident').length
    const urgent = visibleRows.filter((r) => isUrgent(r)).length
    return { tickets, incidents, urgent }
  }, [visibleRows])

  const load = useCallback(async () => {
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
  }, [recordType, status, moduleFilter, dateFrom, dateTo, therapistId, childId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
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

  function clearFilters() {
    setRecordType('all')
    setStatus('')
    setModuleFilter('')
    setDateFrom('')
    setDateTo('')
    setTherapistId('')
    setChildId('')
    setSearch('')
  }

  const filterGrid = (
    <AdminFilterGrid ariaLabel="Support history filters">
      <FilterSelect
        label="Type"
        value={recordType}
        onChange={(e) => setRecordType(e.target.value)}
        options={RECORD_TYPE_OPTIONS}
      />
      <FilterSelect
        label="Status"
        value={status}
        onChange={(e) => setStatus(e.target.value)}
        options={STATUS_OPTIONS}
      />
      <FilterSelect
        label="Service"
        value={moduleFilter}
        onChange={(e) => setModuleFilter(e.target.value)}
        options={moduleOptions}
      />
      <FilterDateRange
        label="Date range"
        from={dateFrom}
        to={dateTo}
        onFromChange={(e) => setDateFrom(e.target.value)}
        onToChange={(e) => setDateTo(e.target.value)}
      />
      <FilterSelect
        label="Therapist"
        value={therapistId}
        onChange={(e) => setTherapistId(e.target.value)}
        options={therapistOptions}
      />
      <FilterSelect
        label="Client"
        value={childId}
        onChange={(e) => setChildId(e.target.value)}
        options={childOptions}
      />
      <div className="admin-filter-grid__actions">
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={clearFilters}>
          Clear filters
        </button>
      </div>
    </AdminFilterGrid>
  )

  return (
    <div className={embedded ? 'admin-hub-embedded' : 'admin-page'}>
      {!embedded ? (
        <AdminPageHeader
          eyebrow="Support"
          title="Support & incident history"
          subtitle="Combined tickets and incident reports across your scope. Monthly clinical reports are under Report management."
          actions={
            <button type="button" className="admin-btn admin-btn--secondary" onClick={exportCsv}>
              Export CSV
            </button>
          }
        />
      ) : null}

      <p className="admin-reports__scope admin-reports__scope--all" role="note" style={{ marginBottom: 12 }}>
        Tickets and incidents only — for monthly and observation reports, open{' '}
        <strong>Report management</strong> in the sidebar.
      </p>

      <div className="admin-reports__kpis" style={{ marginBottom: 16 }}>
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{loading ? '…' : total}</div>
          <div className="admin-reports__kpi-label">Matching records</div>
        </div>
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{loading ? '…' : kpis.tickets}</div>
          <div className="admin-reports__kpi-label">Tickets (shown)</div>
        </div>
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{loading ? '…' : kpis.incidents}</div>
          <div className="admin-reports__kpi-label">Incidents (shown)</div>
        </div>
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{loading ? '…' : kpis.urgent}</div>
          <div className="admin-reports__kpi-label">Needs attention</div>
        </div>
      </div>

      <AdminPanel
        title={`${visibleRows.length} shown`}
        padded={false}
        actions={
          embedded ? (
            <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={exportCsv}>
              Export CSV
            </button>
          ) : null
        }
      >
        <div className="admin-panel__body admin-panel__body--flush">
          <AdminCollapsibleFilters
            quickSearch={
              <AdminSearchInput value={search} onChange={setSearch} placeholder="Search code, subject, client…" />
            }
            activeChips={activeChips}
            activeCount={activeChips.filter((c) => !c.startsWith('Search:')).length}
          >
            {filterGrid}
          </AdminCollapsibleFilters>

          {loading ? (
            <div className="admin-skeleton" style={{ margin: '0 16px 16px' }} />
          ) : visibleRows.length === 0 ? (
            <div style={{ padding: '0 16px 16px' }}>
              <AdminEmptyState
                title="No records"
                hints={['Widen the date range', 'Clear status or service filters', 'Try All types']}
              />
            </div>
          ) : (
            <AdminDataList
              desktop={
                <div className="admin-table-wrap" style={{ padding: '0 16px 16px' }}>
                  <table className="admin-table admin-reports__table-wrap" style={{ width: '100%', fontSize: '0.8rem' }}>
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
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRows.map((r) => (
                        <tr key={`${r.record_type}-${r.id}`} className={isUrgent(r) ? 'sessions-dash__row--highlight' : ''}>
                          <td>{r.record_type === 'incident' ? 'Incident' : 'Ticket'}</td>
                          <td style={{ fontFamily: 'monospace' }}>{r.code}</td>
                          <td>{r.subject}</td>
                          <td>
                            <StatusBadge status={r.status} />
                          </td>
                          <td>{r.priority || '—'}</td>
                          <td>{r.client_name || '—'}</td>
                          <td>{r.therapist_name || '—'}</td>
                          <td>{r.reporter_name || '—'}</td>
                          <td>{r.assignee_name || '—'}</td>
                          <td>{r.product_module ? String(r.product_module).replace(/_/g, ' ') : '—'}</td>
                          <td>{formatDate(r.created_at)}</td>
                          <td>{formatDate(r.closed_at)}</td>
                          <td>{historyRowActions(r)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              }
              mobile={
                <ul className="admin-data-list__cards" style={{ padding: '0 16px 16px' }}>
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
                        <div style={{ marginTop: 8 }}>{historyRowActions(r)}</div>
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
