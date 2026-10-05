import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState } from './ui/index.js'
import { formatDateTimeIN, formatApiDateIN } from '../../lib/datetime.js'
import './admin-hr-reports.css'

export function AdminTherapistAttentionPage() {
  const [page, setPage] = useState(1)
  const [windowDays, setWindowDays] = useState(14)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    apiFetch(`/api/v1/admin/leadership/therapist-attention?page=${page}&page_size=50&window_days=${windowDays}`)
      .then((payload) => {
        setData(payload)
        setError('')
      })
      .catch((err) => {
        setData(null)
        setError(err.message || 'Looks like we still need a few details before we can show this report.')
      })
      .finally(() => setLoading(false))
  }, [page, windowDays])

  const rows = data?.rows || []
  const total = data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(total / (data?.pageSize || 50)))

  return (
    <div className="admin-page admin-hr-reports">
      <AdminPageHeader
        eyebrow="Therapists"
        title="Therapist attention"
        subtitle="Account, assignment, last login, last app activity, and missing logs. Login is not app usage."
      />
      <AdminPanel padded>
        {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
        <p className="admin-muted">{data?.loginNote}</p>
        <div className="admin-hr-reports__filters">
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Activity gap window (days)</span>
            <select
              className="client-inv__filter-input"
              value={windowDays}
              onChange={(e) => {
                setWindowDays(Number(e.target.value))
                setPage(1)
              }}
            >
              <option value={7}>7</option>
              <option value={14}>14</option>
              <option value={30}>30</option>
            </select>
          </label>
        </div>
        {loading ? <p className="admin-muted">Loading…</p> : null}
        {!loading && !rows.length ? (
          <AdminEmptyState title="No therapist rows" description="No therapists are in this organisation view." />
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
                  <th>Therapist</th>
                  <th>Account</th>
                  <th>Assignments</th>
                  <th>Last login</th>
                  <th>Last app activity</th>
                  <th>Last completed session</th>
                  <th>Missing logs</th>
                  <th>Profile</th>
                  <th>Gaps</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.userId}>
                    <td>
                      <Link to={row.href}>{row.fullName}</Link>
                      <div className="admin-muted">#{row.userId}</div>
                    </td>
                    <td>
                      {row.accountActive ? 'Active' : 'Inactive'} · {row.employmentStatus}
                    </td>
                    <td>{row.activeAssignmentCount}</td>
                    <td>{formatDateTimeIN(row.lastLoginAt) || 'No recorded login'}</td>
                    <td>{formatDateTimeIN(row.lastAppActivityAt) || 'No recorded activity'}</td>
                    <td>{formatApiDateIN(row.lastCompletedSessionDate) || '—'}</td>
                    <td>{row.completedSessionsMissingLogs}</td>
                    <td>
                      {row.profileStatus}
                      {row.pendingProfileChanges ? ' · pending edits' : ''}
                    </td>
                    <td>{(row.gaps || []).join(', ') || '—'}</td>
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
