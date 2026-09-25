import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { formatDateIN } from '../../lib/datetime.js'
import { isSpotOnlyUser } from '../../lib/spotPortal.js'
import {
  createStaffLeave,
  fetchMyStaffAttendance,
  fetchMyStaffLeaves,
  fetchStaffLeaveBalance,
} from '../../lib/staffAttendanceApi.js'
import { StaffTimerPanel } from './StaffTimerPanel.jsx'
import { AdminEmptyState, AdminPageHeader, AdminPanel, StatusBadge } from './ui/index.js'
import './staff-attendance.css'

const LEAVE_STATUS_TONE = {
  PENDING: 'amber',
  APPROVED: 'green',
  REJECTED: 'rose',
  CANCELLED: 'zinc',
}

export function SpotDashboardPage() {
  const { user } = useAuth()
  if (!isSpotOnlyUser(user)) return <Navigate to="/admin" replace />

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="SPOT School"
        title={`Good day${user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}`}
        subtitle="Clock in when you start, and clock out when you finish."
      />
      <StaffTimerPanel title="Start your day" />
    </div>
  )
}

export function SpotAttendancePage() {
  const { user } = useAuth()
  const [rows, setRows] = useState([])
  const [leaves, setLeaves] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [att, leaveRows] = await Promise.all([
        fetchMyStaffAttendance({ limit: 60 }),
        fetchMyStaffLeaves(),
      ])
      setRows(att?.items || [])
      setLeaves(Array.isArray(leaveRows) ? leaveRows : [])
    } catch (err) {
      setError(err.message || 'Could not load attendance.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isSpotOnlyUser(user)) load()
  }, [user, load])

  if (!isSpotOnlyUser(user)) return <Navigate to="/admin" replace />

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="SPOT School"
        title="Attendance"
        subtitle="Your session history and leave records."
      />
      {error ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {error}
        </p>
      ) : null}

      <AdminPanel title="Session history" padded={false}>
        {loading ? (
          <p className="admin-muted" style={{ padding: '1rem' }}>
            Loading…
          </p>
        ) : rows.length === 0 ? (
          <AdminEmptyState title="No sessions yet" description="Clock in from your dashboard to start tracking." />
        ) : (
          <div className="staff-attendance-table-wrap">
            <table className="staff-attendance-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Status</th>
                  <th>Working time</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{formatDateIN(`${row.work_date}T12:00:00Z`) || row.work_date}</td>
                    <td>{row.status?.replace(/_/g, ' ') || '—'}</td>
                    <td>{row.total_work_seconds ? `${Math.floor(row.total_work_seconds / 3600)}h ${Math.floor((row.total_work_seconds % 3600) / 60)}m` : '—'}</td>
                    <td>{row.work_summary || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AdminPanel>

      <AdminPanel title="Your leave" style={{ marginTop: 16 }}>
        {leaves.length === 0 ? (
          <AdminEmptyState title="No leave yet" description="Submitted requests will appear here." />
        ) : (
          <ul className="admin-data-list__cards">
            {leaves.map((row) => (
              <li key={row.id} className="staff-attendance-mobile-card">
                <div className="staff-attendance-mobile-card__meta">
                  <strong>{formatDateIN(`${row.leave_date}T12:00:00Z`) || row.leave_date}</strong>
                  <StatusBadge tone={LEAVE_STATUS_TONE[row.status] || 'zinc'}>{row.status}</StatusBadge>
                  {row.billing_category ? (
                    <StatusBadge tone={row.billing_category === 'PAID' ? 'green' : 'zinc'}>
                      {row.billing_category === 'PAID' ? 'Paid' : 'Unpaid'}
                    </StatusBadge>
                  ) : null}
                </div>
                <p className="admin-muted" style={{ margin: 0 }}>
                  {row.reason}
                </p>
              </li>
            ))}
          </ul>
        )}
      </AdminPanel>
    </div>
  )
}

export function SpotLeavePage() {
  const { user } = useAuth()
  const [leaveForm, setLeaveForm] = useState({ leave_date: '', reason: '' })
  const [balance, setBalance] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    if (!isSpotOnlyUser(user)) return
    fetchStaffLeaveBalance()
      .then(setBalance)
      .catch(() => setBalance(null))
  }, [user])

  if (!isSpotOnlyUser(user)) return <Navigate to="/admin" replace />

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      await createStaffLeave(leaveForm)
      setSuccess('Leave request sent to HR.')
      setLeaveForm({ leave_date: '', reason: '' })
      const nextBalance = await fetchStaffLeaveBalance()
      setBalance(nextBalance)
    } catch (err) {
      setError(err.message || 'Could not submit leave.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="SPOT School"
        title="Request leave"
        subtitle="Full-day leave — HR will review your request."
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

      {balance ? (
        <AdminPanel title="Leave balance" style={{ marginBottom: 16 }}>
          <p className="admin-muted" style={{ margin: 0 }}>
            Paid credits remaining: <strong>{balance.leave_credit_balance ?? 0}</strong>
            {balance.on_probation ? (
              <span> · During probation: up to 1 paid leave per month.</span>
            ) : null}
          </p>
        </AdminPanel>
      ) : null}

      <AdminPanel title="Submit leave">
        <form onSubmit={handleSubmit} className="staff-attendance-edit-grid">
          <label className="admin-filter-field">
            <span className="admin-filter-field__label">Date</span>
            <input
              type="date"
              className="admin-input"
              value={leaveForm.leave_date}
              onChange={(e) => setLeaveForm((f) => ({ ...f, leave_date: e.target.value }))}
              required
            />
          </label>
          <label className="admin-filter-field" style={{ gridColumn: '1 / -1' }}>
            <span className="admin-filter-field__label">Reason</span>
            <textarea
              className="admin-input"
              value={leaveForm.reason}
              onChange={(e) => setLeaveForm((f) => ({ ...f, reason: e.target.value }))}
              required
              minLength={3}
              placeholder="Share what you need time off for…"
            />
          </label>
          <div style={{ gridColumn: '1 / -1' }}>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={busy}>
              {busy ? 'Sending…' : 'Submit leave'}
            </button>
          </div>
        </form>
      </AdminPanel>
    </div>
  )
}
