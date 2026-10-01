import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDateIN, formatTimeIST } from '../../lib/datetime.js'
import { canManageStaffAttendance } from '../../lib/staffAttendanceAccess.js'
import {
  exportUserStaffAttendanceCsv,
  fetchUserStaffAttendance,
  formatDurationSeconds,
  hrUpdateStaffAttendance,
} from '../../lib/staffAttendanceApi.js'
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminPanel,
  AdminSearchInput,
  AdminToolbar,
  PortalTabBar,
  StatusBadge,
} from './ui/index.js'
import { FilterSelect } from './ui/FilterSelect.jsx'
import { PeopleListPagination } from './ui/PeopleListPagination.jsx'
import './staff-attendance.css'

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'completed_logs', label: 'Completed logs' },
  { value: 'leaves', label: 'Leaves' },
]

const PAGE_SIZE = 25

function entryTone(row) {
  if (row.record_kind === 'leave') return 'amber'
  if (row.entry_type === 'FORGOT') return 'rose'
  if (row.status === 'AUTO_CLOSED') return 'zinc'
  if (row.status === 'COMPLETED') return 'green'
  return 'blue'
}

export function AdminStaffAttendanceDetailPage() {
  const { userId } = useParams()
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const filter = searchParams.get('filter') || 'all'
  const [staffUser, setStaffUser] = useState(null)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [editing, setEditing] = useState(null)
  const [editForm, setEditForm] = useState({ work_summary: '' })
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search), 300)
    return () => window.clearTimeout(t)
  }, [search])

  const loadStaff = useCallback(async () => {
    try {
      const data = await apiFetch(`/api/v1/admin/users/${userId}`)
      setStaffUser(data)
    } catch {
      setStaffUser(null)
    }
  }, [userId])

  const loadRecords = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchUserStaffAttendance(Number(userId), {
        filter,
        search: debouncedSearch,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      })
      setItems(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      setItems([])
      setTotal(0)
      setError(err.message || 'Could not load attendance.')
    } finally {
      setLoading(false)
    }
  }, [userId, filter, debouncedSearch, page])

  useEffect(() => {
    if (!canManageStaffAttendance(user)) return
    loadStaff()
  }, [user, loadStaff])

  useEffect(() => {
    if (!canManageStaffAttendance(user)) return
    loadRecords()
  }, [user, loadRecords])

  if (!canManageStaffAttendance(user)) {
    return <Navigate to="/admin/people?tab=staff" replace />
  }

  function setFilter(next) {
    setPage(1)
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('filter', next)
    setSearchParams(nextParams)
  }

  async function handleExport() {
    try {
      await exportUserStaffAttendanceCsv(Number(userId), { filter, search: debouncedSearch })
    } catch (err) {
      setError(err.message || 'Export failed.')
    }
  }

  async function saveEdit() {
    if (!editing) return
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      await hrUpdateStaffAttendance(editing.id, { work_summary: editForm.work_summary })
      setSuccess('Attendance updated.')
      setEditing(null)
      await loadRecords()
    } catch (err) {
      setError(err.message || 'Could not update record.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="People & HR"
        title={staffUser?.full_name ? `${staffUser.full_name} — Attendance` : 'Staff attendance'}
        subtitle={staffUser?.email || ''}
        actions={
          <div className="admin-btn-group">
            <Link to="/admin/people?tab=staff" className="admin-btn admin-btn--ghost admin-btn--sm">
              Back to People
            </Link>
            <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={handleExport}>
              Export CSV
            </button>
          </div>
        }
      />

      {error ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="admin-alert admin-alert--success" role="status">
          {success}
        </p>
      ) : null}

      <AdminToolbar>
        <AdminSearchInput
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          placeholder="Search date, summary, reason…"
          aria-label="Search attendance"
        />
        <FilterSelect
          label="Filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          options={FILTERS}
        />
      </AdminToolbar>

      <PortalTabBar
        ariaLabel="Attendance filters"
        activeId={filter}
        onChange={setFilter}
        tabs={FILTERS.map((f) => ({ id: f.value, label: f.label }))}
      />

      <AdminPanel>
        {loading ? <p className="admin-muted">Loading…</p> : null}
        {!loading && items.length === 0 ? (
          <AdminEmptyState title="No records" description="Try another filter or search term." />
        ) : null}
        {!loading && items.length > 0 ? (
          <>
            <div className="staff-attendance-table-wrap admin-hide-mobile">
              <table className="staff-attendance-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Day</th>
                    <th>Type</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>Total</th>
                    <th>Summary</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={`${row.record_kind}-${row.id}`}>
                      <td>{formatDateIN(`${row.work_date}T12:00:00Z`) || row.work_date}</td>
                      <td>{row.day_name}</td>
                      <td>
                        <StatusBadge tone={entryTone(row)}>
                          {row.record_kind === 'leave' ? 'LEAVE' : row.entry_type}
                        </StatusBadge>
                      </td>
                      <td>{row.clock_in_at ? formatTimeIST(row.clock_in_at) : '—'}</td>
                      <td>{row.clock_out_at ? formatTimeIST(row.clock_out_at) : '—'}</td>
                      <td>{formatDurationSeconds(row.total_work_seconds)}</td>
                      <td>
                        <div>{row.work_summary || '—'}</div>
                        {row.forgot_reason ? (
                          <p className="admin-muted" style={{ margin: '4px 0 0', fontSize: '0.85rem' }}>
                            Reason: {row.forgot_reason}
                          </p>
                        ) : null}
                        {row.record_kind === 'leave' ? (
                          <StatusBadge tone={entryTone(row)}>{row.status}</StatusBadge>
                        ) : null}
                      </td>
                      <td>
                        {row.record_kind === 'attendance' ? (
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            onClick={() => {
                              setEditing(row)
                              setEditForm({ work_summary: row.work_summary || '' })
                            }}
                          >
                            Edit
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="admin-show-mobile admin-data-list__cards">
              {items.map((row) => (
                <li key={`${row.record_kind}-${row.id}-m`} className="staff-attendance-mobile-card">
                  <div className="staff-attendance-mobile-card__meta">
                    <strong>{formatDateIN(`${row.work_date}T12:00:00Z`) || row.work_date}</strong>
                    <span className="admin-muted">{row.day_name}</span>
                    <StatusBadge tone={entryTone(row)}>
                      {row.record_kind === 'leave' ? `LEAVE · ${row.status}` : row.entry_type}
                    </StatusBadge>
                  </div>
                  <p className="admin-muted" style={{ margin: '0 0 6px' }}>
                    {row.clock_in_at ? formatTimeIST(row.clock_in_at) : '—'} →{' '}
                    {row.clock_out_at ? formatTimeIST(row.clock_out_at) : '—'} · Total{' '}
                    {formatDurationSeconds(row.total_work_seconds)}
                  </p>
                  <p style={{ margin: 0 }}>{row.work_summary || '—'}</p>
                  {row.record_kind === 'attendance' ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      style={{ marginTop: 8 }}
                      onClick={() => {
                        setEditing(row)
                        setEditForm({ work_summary: row.work_summary || '' })
                      }}
                    >
                      Edit
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>

            <PeopleListPagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
          </>
        ) : null}
      </AdminPanel>

      {editing ? (
        <div className="staff-attendance-modal-backdrop" role="presentation" onClick={() => setEditing(null)}>
          <div
            className="staff-attendance-modal"
            role="dialog"
            aria-labelledby="edit-attendance-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="edit-attendance-title" className="staff-attendance-modal__title">
              Edit attendance log
            </h3>
            <p className="admin-muted">
              {formatDateIN(`${editing.work_date}T12:00:00Z`) || editing.work_date} · {editing.day_name}
            </p>
            <label className="admin-filter-field">
              <span className="admin-filter-field__label">Work summary</span>
              <textarea
                className="admin-input"
                value={editForm.work_summary}
                onChange={(e) => setEditForm({ work_summary: e.target.value })}
                rows={4}
              />
            </label>
            <div className="admin-btn-group" style={{ marginTop: 12 }}>
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={busy} onClick={saveEdit}>
                Save
              </button>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setEditing(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
