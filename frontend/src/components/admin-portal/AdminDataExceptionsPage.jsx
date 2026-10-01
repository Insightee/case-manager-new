import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState } from './ui/index.js'
import './admin-hr-reports.css'

export function AdminDataExceptionsPage() {
  const [page, setPage] = useState(1)
  const [confirmation, setConfirmation] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    const qs = new URLSearchParams({ page: String(page), page_size: '50' })
    if (confirmation) qs.set('confirmation', confirmation)
    apiFetch(`/api/v1/admin/leadership/data-exceptions?${qs.toString()}`)
      .then((payload) => {
        setData(payload)
        setError('')
      })
      .catch((err) => {
        setData(null)
        setError(err.message || 'Looks like we still need a few details before we can show this report.')
      })
      .finally(() => setLoading(false))
  }, [page, confirmation])

  const rows = data?.rows || []
  const total = data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(total / (data?.pageSize || 50)))

  return (
    <div className="admin-page admin-hr-reports">
      <AdminPageHeader
        eyebrow="Data quality"
        title="Data exceptions"
        subtitle="Live Layer-1 checks as of generation. Nothing is auto-repaired."
      />
      <AdminPanel padded>
        {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
        <p className="admin-muted">{data?.note}</p>
        <div className="admin-hr-reports__filters">
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Confirmation</span>
            <select
              className="client-inv__filter-input"
              value={confirmation}
              onChange={(e) => {
                setConfirmation(e.target.value)
                setPage(1)
              }}
            >
              <option value="">All</option>
              <option value="confirmed">Confirmed</option>
              <option value="suspected">Suspected</option>
            </select>
          </label>
        </div>
        {loading ? <p className="admin-muted">Loading…</p> : null}
        {!loading && !rows.length ? (
          <AdminEmptyState title="No exceptions in this filter" description="The live checks did not flag rows for this view." />
        ) : null}
        {rows.length ? (
          <div className="admin-table-wrap">
            <p className="admin-muted">
              Showing {rows.length} of {total}
              {data?.previewLimited ? ' — this page is not the full list.' : '.'} As of {data?.asOf}.
            </p>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Confirmation</th>
                  <th>Record</th>
                  <th>Dates</th>
                  <th>Owner</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.rule}-${row.recordType}-${row.recordId}-${row.label}`}>
                    <td>
                      {row.rule}
                      <div className="admin-muted">{row.severity}</div>
                    </td>
                    <td>{row.confirmation}</td>
                    <td>
                      <Link to={row.href}>{row.label}</Link>
                    </td>
                    <td>{row.dates || '—'}</td>
                    <td>{row.owner}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {totalPages > 1 ? (
              <div className="admin-btn-group" style={{ marginTop: 12 }}>
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Previous
                </button>
                <span className="admin-muted">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </AdminPanel>
    </div>
  )
}
