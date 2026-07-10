import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import './admin-client-status.css'

const STATUS_LABELS = {
  ACTIVE: 'Active',
  PENDING_ALLOTMENT: 'Pending allotment',
  SUSPENDED: 'Suspended',
  PENDING_REPLACEMENT: 'Pending replacement',
  CLOSED: 'Closed',
  DEACTIVATED: 'Closed (legacy)',
}

function StatusBadge({ status }) {
  const key = (status || 'ACTIVE').toLowerCase()
  return (
    <span className={`cs-badge cs-badge--${key}`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

export function AdminClientStatusReportSection() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 25, pages: 1 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters state
  const [statusFilter, setStatusFilter] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [cmFilter, setCmFilter] = useState('')
  const [serviceTypeSearch, setServiceTypeSearch] = useState('')
  const [ageingFilter, setAgeingFilter] = useState('')
  const [page, setPage] = useState(1)

  // Directory lists
  const [cms, setCms] = useState([])

  // Load case managers directory
  useEffect(() => {
    apiFetch('/api/v1/admin/users/directory?roles=CASE_MANAGER')
      .then((users) => {
        setCms(users || [])
      })
      .catch((err) => console.error('Could not load case managers directory', err))
  }, [])

  const loadReport = useCallback(() => {
    setLoading(true)
    setError('')
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    if (fromDate) params.set('from_date', fromDate)
    if (toDate) params.set('to_date', toDate)
    if (cmFilter) params.set('case_manager_user_id', cmFilter)
    if (serviceTypeSearch) params.set('service_type', serviceTypeSearch)
    if (ageingFilter) params.set('ageing_gt_days', ageingFilter)
    params.set('page', String(page))
    params.set('page_size', '25')

    apiFetch(`/api/v1/admin/reports/client-status?${params.toString()}`)
      .then(setData)
      .catch((err) => setError(err.message || 'Could not load client status report'))
      .finally(() => setLoading(false))
  }, [statusFilter, fromDate, toDate, cmFilter, serviceTypeSearch, ageingFilter, page])

  useEffect(() => {
    loadReport()
  }, [loadReport])

  const handleFilterChange = (setter, value) => {
    setter(value)
    setPage(1)
  }

  return (
    <div className="admin-panel" style={{ padding: '24px' }}>
      <h2 style={{ margin: '0 0 20px', fontSize: '1.25rem', fontWeight: 700 }}>Client Status Lifecycle Report</h2>

      <div className="cs-report__filters">
        <div className="cs-report__filter-group">
          <span className="cs-report__filter-label">Current Status</span>
          <select
            className="admin-input"
            style={{ width: '180px' }}
            value={statusFilter}
            onChange={(e) => handleFilterChange(setStatusFilter, e.target.value)}
          >
            <option value="">All Statuses</option>
            {Object.entries(STATUS_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
        </div>

        <div className="cs-report__filter-group">
          <span className="cs-report__filter-label">From Date</span>
          <input
            type="date"
            className="admin-input"
            value={fromDate}
            onChange={(e) => handleFilterChange(setFromDate, e.target.value)}
          />
        </div>

        <div className="cs-report__filter-group">
          <span className="cs-report__filter-label">To Date</span>
          <input
            type="date"
            className="admin-input"
            value={toDate}
            onChange={(e) => handleFilterChange(setToDate, e.target.value)}
          />
        </div>

        <div className="cs-report__filter-group">
          <span className="cs-report__filter-label">Case Manager</span>
          <select
            className="admin-input"
            style={{ width: '180px' }}
            value={cmFilter}
            onChange={(e) => handleFilterChange(setCmFilter, e.target.value)}
          >
            <option value="">All Case Managers</option>
            {cms.map((user) => (
              <option key={user.id} value={user.id}>{user.fullName}</option>
            ))}
          </select>
        </div>

        <div className="cs-report__filter-group">
          <span className="cs-report__filter-label">Service Type</span>
          <input
            type="text"
            className="admin-input"
            placeholder="Search service type..."
            style={{ width: '180px' }}
            value={serviceTypeSearch}
            onChange={(e) => handleFilterChange(setServiceTypeSearch, e.target.value)}
          />
        </div>

        <div className="cs-report__filter-group">
          <span className="cs-report__filter-label">Ageing (days &gt;)</span>
          <input
            type="number"
            min="0"
            className="admin-input"
            placeholder="e.g. 7"
            style={{ width: '110px' }}
            value={ageingFilter}
            onChange={(e) => handleFilterChange(setAgeingFilter, e.target.value)}
          />
        </div>

        <button
          type="button"
          className="admin-btn admin-btn--secondary"
          onClick={() => {
            setStatusFilter('')
            setFromDate('')
            setToDate('')
            setCmFilter('')
            setServiceTypeSearch('')
            setAgeingFilter('')
            setPage(1)
          }}
        >
          Clear Filters
        </button>
      </div>

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      {loading ? (
        <p className="admin-muted" style={{ padding: '20px 0' }}>Loading report data...</p>
      ) : !data.items?.length ? (
        <div className="cs-report__empty">
          No clients found matching the selected filters.
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto', marginTop: '16px' }}>
            <table className="cs-report__table">
              <thead>
                <tr>
                  <th>Client Name</th>
                  <th>Case Code</th>
                  <th>Service Type</th>
                  <th>Current Status</th>
                  <th>Effective Date</th>
                  <th>Change Reason</th>
                  <th>Ageing</th>
                  <th>Last Updated By</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.caseId}>
                    <td style={{ fontWeight: 600 }}>{row.clientName || '—'}</td>
                    <td>{row.caseCode}</td>
                    <td>{row.serviceType}</td>
                    <td><StatusBadge status={row.currentStatus} /></td>
                    <td>{row.statusEffectiveDate || '—'}</td>
                    <td style={{ maxWidth: '240px', wordBreak: 'break-word' }}>
                      {row.statusReason || '—'}
                    </td>
                    <td>
                      {row.ageingDays !== null ? (
                        <span
                          className="cs-audit__ageing"
                          style={{
                            color: row.ageingDays > 7 ? '#ef4444' : '#b45309',
                            fontWeight: row.ageingDays > 7 ? 700 : 500
                          }}
                        >
                          ⏱️ {row.ageingDays} days
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <div>{row.lastUpdatedBy || '—'}</div>
                      <div style={{ fontSize: '0.72rem', color: '#64748b' }}>
                        {row.lastChangedAt ? new Date(row.lastChangedAt).toLocaleString() : ''}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.pages > 1 ? (
            <div className="admin-pagination" style={{ marginTop: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="admin-muted" style={{ fontSize: '0.8rem' }}>
                Showing page {data.page} of {data.pages} (Total: {data.total} records)
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  disabled={page === data.pages}
                  onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}
