import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { formatDateIN } from '../../lib/datetime.js'
import { isStaffAttendanceUser } from '../../lib/staffAttendanceAccess.js'
import {
  createStaffLeave,
  fetchMyStaffAttendance,
  fetchMyStaffLeaves,
} from '../../lib/staffAttendanceApi.js'
import { StaffAttendanceHistory } from './StaffAttendanceHistory.jsx'
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminPanel,
  PortalTabBar,
  StatusBadge,
} from './ui/index.js'
import './staff-attendance.css'

const MODES = [
  { id: 'records', label: 'Records' },
  { id: 'leave', label: 'Leave' },
]

const LEAVE_STATUS_TONE = {
  PENDING: 'amber',
  APPROVED: 'green',
  REJECTED: 'rose',
  CANCELLED: 'zinc',
}

export function StaffAttendancePage() {
  const { user } = useAuth()
  const [mode, setMode] = useState('records')
  const [rows, setRows] = useState([])
  const [myLeaves, setMyLeaves] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [leaveForm, setLeaveForm] = useState({ leave_date: '', reason: '' })

  const loadRecords = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [att, leaveRows] = await Promise.all([
        fetchMyStaffAttendance({ limit: 60 }),
        fetchMyStaffLeaves(),
      ])
      setRows(att?.items || [])
      setMyLeaves(Array.isArray(leaveRows) ? leaveRows : [])
    } catch (err) {
      setError(err.message || 'Could not load attendance.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isStaffAttendanceUser(user)) loadRecords()
  }, [user, loadRecords])

  if (!isStaffAttendanceUser(user)) {
    return <Navigate to="/admin" replace />
  }

  async function handleLeaveSubmit(e) {
    e.preventDefault()
    setBusy('leave')
    setError('')
    setSuccess('')
    try {
      await createStaffLeave(leaveForm)
      setSuccess('Leave request sent to HR.')
      setLeaveForm({ leave_date: '', reason: '' })
      await loadRecords()
    } catch (err) {
      setError(err.message || 'Could not submit leave.')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="People & HR"
        title="Attendance"
        subtitle="Your session history and leave requests. Clock in from your dashboard."
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

      <PortalTabBar ariaLabel="Attendance sections" activeId={mode} onChange={setMode} tabs={MODES} />

      {mode === 'records' ? (
        <StaffAttendanceHistory rows={rows} loading={loading} />
      ) : null}

      {mode === 'leave' ? (
        <>
          <AdminPanel title="Request leave" subtitle="Full-day leave — HR will review your request.">
            <form onSubmit={handleLeaveSubmit} className="staff-attendance-edit-grid">
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
                <button type="submit" className="admin-btn admin-btn--primary" disabled={busy === 'leave'}>
                  Submit leave
                </button>
              </div>
            </form>
          </AdminPanel>

          <AdminPanel title="Your leave requests" style={{ marginTop: 16 }}>
            {myLeaves.length === 0 ? (
              <AdminEmptyState title="No leave yet" description="Submitted requests will appear here." />
            ) : (
              <ul className="admin-data-list__cards">
                {myLeaves.map((row) => (
                  <li key={row.id} className="staff-attendance-mobile-card">
                    <div className="staff-attendance-mobile-card__meta">
                      <strong>{formatDateIN(`${row.leave_date}T12:00:00Z`) || row.leave_date}</strong>
                      <StatusBadge tone={LEAVE_STATUS_TONE[row.status] || 'zinc'}>{row.status}</StatusBadge>
                    </div>
                    <p className="admin-muted" style={{ margin: 0 }}>
                      {row.reason}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </AdminPanel>
        </>
      ) : null}
    </div>
  )
}
