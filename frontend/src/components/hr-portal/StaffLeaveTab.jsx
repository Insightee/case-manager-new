import { useCallback, useEffect, useState } from 'react'
import {
  AdminEmptyState,
  AdminPanel,
  AdminSearchInput,
  AdminToolbar,
  PortalTabBar,
  RejectWithComment,
  StatusBadge,
} from '../admin-portal/ui/index.js'
import { PeopleListPagination } from '../admin-portal/ui/PeopleListPagination.jsx'
import { formatDateIN } from '../../lib/datetime.js'
import { fetchStaffLeavesAdmin, reviewStaffLeave } from '../../lib/staffAttendanceApi.js'

const REVIEW_TABS = [
  ['PENDING', 'Pending'],
  ['APPROVED', 'Approved'],
  ['REJECTED', 'Rejected'],
  ['ALL', 'All'],
]

const STATUS_TONE = {
  PENDING: 'amber',
  APPROVED: 'green',
  REJECTED: 'rose',
  CANCELLED: 'zinc',
}

const PAGE_SIZE = 25

export function StaffLeaveTab() {
  const [status, setStatus] = useState('PENDING')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [counts, setCounts] = useState({ PENDING: 0, APPROVED: 0, REJECTED: 0, ALL: 0 })
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState({})
  const [rejectingId, setRejectingId] = useState(null)
  const [rejectComment, setRejectComment] = useState('')

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(search), 300)
    return () => window.clearTimeout(t)
  }, [search])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchStaffLeavesAdmin({
        status,
        search: debouncedSearch,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      })
      setItems(data.items || [])
      setTotal(data.total || 0)
      setCounts(data.status_counts || {})
    } catch (err) {
      setItems([])
      setError(err.message || 'Could not load staff leave.')
    } finally {
      setLoading(false)
    }
  }, [status, debouncedSearch, page])

  useEffect(() => {
    load()
  }, [load])

  async function act(leaveId, nextStatus, note) {
    setProcessing((p) => ({ ...p, [leaveId]: true }))
    setError('')
    try {
      await reviewStaffLeave(leaveId, { status: nextStatus, review_note: note })
      setRejectingId(null)
      setRejectComment('')
      await load()
    } catch (err) {
      setError(err.message || 'Review failed.')
    } finally {
      setProcessing((p) => ({ ...p, [leaveId]: false }))
    }
  }

  return (
    <div>
      {error ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {error}
        </p>
      ) : null}

      <AdminToolbar>
        <AdminSearchInput
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
          placeholder="Search staff name or reason…"
          aria-label="Search staff leave"
        />
      </AdminToolbar>

      <PortalTabBar
        ariaLabel="Staff leave status"
        activeId={status}
        onChange={(id) => {
          setStatus(id)
          setPage(1)
        }}
        tabs={REVIEW_TABS.map(([id, label]) => ({
          id,
          label: `${label}${counts[id] != null ? ` (${counts[id]})` : ''}`,
        }))}
      />

      <AdminPanel title="Staff leave">
        {loading ? <p className="admin-muted">Loading…</p> : null}
        {!loading && items.length === 0 ? (
          <AdminEmptyState title="No staff leave here" description="Requests will show up when staff submit leave." />
        ) : null}
        {!loading && items.length > 0 ? (
          <ul className="admin-data-list__cards">
            {items.map((row) => (
              <li key={row.id} className="staff-attendance-mobile-card">
                <div className="staff-attendance-mobile-card__meta">
                  <strong>{row.staff_name}</strong>
                  <StatusBadge tone={STATUS_TONE[row.status] || 'zinc'}>{row.status}</StatusBadge>
                </div>
                <p className="admin-muted" style={{ margin: '0 0 6px' }}>
                  {formatDateIN(`${row.leave_date}T12:00:00Z`) || row.leave_date} · {row.day_name}
                </p>
                <p style={{ margin: 0 }}>{row.reason}</p>
                {row.status === 'PENDING' ? (
                  <div className="admin-btn-group" style={{ marginTop: 10 }}>
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary admin-btn--sm"
                      disabled={!!processing[row.id]}
                      onClick={() => act(row.id, 'APPROVED')}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="admin-btn admin-btn--secondary admin-btn--sm"
                      disabled={!!processing[row.id]}
                      onClick={() => setRejectingId(row.id)}
                    >
                      Reject
                    </button>
                  </div>
                ) : null}
                {rejectingId === row.id ? (
                  <RejectWithComment
                    comment={rejectComment}
                    onCommentChange={setRejectComment}
                    onConfirm={() => act(row.id, 'REJECTED', rejectComment)}
                    onCancel={() => {
                      setRejectingId(null)
                      setRejectComment('')
                    }}
                    busy={!!processing[row.id]}
                  />
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
        <PeopleListPagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      </AdminPanel>
    </div>
  )
}
