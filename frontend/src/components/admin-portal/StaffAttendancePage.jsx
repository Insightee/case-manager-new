import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { formatDateIN, formatTimeIST, todayIsoIST } from '../../lib/datetime.js'
import { isStaffAttendanceUser } from '../../lib/staffAttendanceAccess.js'
import {
  clockInStaff,
  clockOutStaff,
  createStaffLeave,
  fetchMyStaffLeaves,
  fetchTodayAttendance,
  formatDurationSeconds,
  pauseStaffAttendance,
  resumeStaffAttendance,
  saveStaffWorkSummary,
  submitForgotStaffLog,
} from '../../lib/staffAttendanceApi.js'
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminPanel,
  PortalTabBar,
  StatusBadge,
} from './ui/index.js'
import './staff-attendance.css'

const MODES = [
  { id: 'start', label: 'Start now' },
  { id: 'forgot', label: 'Forgot to log' },
  { id: 'leave', label: 'Leave' },
]

const LEAVE_STATUS_TONE = {
  PENDING: 'amber',
  APPROVED: 'green',
  REJECTED: 'rose',
  CANCELLED: 'zinc',
}

function isoFromDateAndTime(dateStr, timeStr) {
  if (!dateStr || !timeStr) return null
  return new Date(`${dateStr}T${timeStr}:00+05:30`).toISOString()
}

export function StaffAttendancePage() {
  const { user } = useAuth()
  const [mode, setMode] = useState('start')
  const [todayState, setTodayState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [workSummary, setWorkSummary] = useState('')
  const [tick, setTick] = useState(0)

  const [forgotForm, setForgotForm] = useState({
    work_date: todayIsoIST(),
    start_time: '09:00',
    end_time: '18:00',
    work_summary: '',
    reason: '',
  })
  const [leaveForm, setLeaveForm] = useState({ leave_date: '', reason: '' })
  const [myLeaves, setMyLeaves] = useState([])

  const loadToday = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchTodayAttendance()
      setTodayState(data)
      setWorkSummary(data?.attendance?.work_summary || '')
    } catch (err) {
      setError(err.message || 'Could not load attendance for today.')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadLeaves = useCallback(async () => {
    try {
      const rows = await fetchMyStaffLeaves()
      setMyLeaves(Array.isArray(rows) ? rows : [])
    } catch {
      setMyLeaves([])
    }
  }, [])

  useEffect(() => {
    if (!isStaffAttendanceUser(user)) return
    loadToday()
    loadLeaves()
  }, [user, loadToday, loadLeaves])

  useEffect(() => {
    if (!todayState?.is_clocked_in && !todayState?.is_paused) return undefined
    const id = window.setInterval(() => {
      setTick((t) => t + 1)
      loadToday()
    }, 30000)
    return () => window.clearInterval(id)
  }, [todayState?.is_clocked_in, todayState?.is_paused, loadToday])

  const attendance = todayState?.attendance
  const isClockedIn = Boolean(todayState?.is_clocked_in)
  const isPaused = Boolean(todayState?.is_paused)
  const hasSessionToday = Boolean(attendance)
  const canClockInAgain = hasSessionToday && !isClockedIn && !isPaused && attendance?.status === 'COMPLETED'

  const liveWorkSeconds = useMemo(() => {
    void tick
    if (!attendance) return 0
    return attendance.total_work_seconds || 0
  }, [attendance, tick])

  const liveBreakSeconds = useMemo(() => {
    void tick
    if (!attendance) return 0
    return attendance.total_break_seconds || 0
  }, [attendance, tick])

  if (!isStaffAttendanceUser(user)) {
    return <Navigate to="/admin" replace />
  }

  async function runAction(actionKey, fn) {
    setBusy(actionKey)
    setError('')
    setSuccess('')
    try {
      const updated = await fn()
      if (updated?.work_summary != null) {
        setWorkSummary(updated.work_summary || '')
      }
      await loadToday()
      setSuccess('Saved.')
    } catch (err) {
      setError(err.message || 'Something went wrong — try again in a moment.')
    } finally {
      setBusy('')
    }
  }

  async function handleForgotSubmit(e) {
    e.preventDefault()
    setBusy('forgot')
    setError('')
    setSuccess('')
    try {
      const startAt = isoFromDateAndTime(forgotForm.work_date, forgotForm.start_time)
      const endAt = isoFromDateAndTime(forgotForm.work_date, forgotForm.end_time)
      await submitForgotStaffLog({
        work_date: forgotForm.work_date,
        start_at: startAt,
        end_at: endAt,
        work_summary: forgotForm.work_summary,
        reason: forgotForm.reason,
      })
      setSuccess('Your late log is recorded.')
      setForgotForm((f) => ({ ...f, work_summary: '', reason: '' }))
      await loadToday()
    } catch (err) {
      setError(err.message || 'Could not save the late log.')
    } finally {
      setBusy('')
    }
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
      await loadLeaves()
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
        subtitle="Clock in, note what you worked on, and request leave when you need it."
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

      <PortalTabBar ariaLabel="Attendance modes" activeId={mode} onChange={setMode} tabs={MODES} />

      {mode === 'start' ? (
        <AdminPanel title="Today's session" subtitle={formatDateIN(`${todayIsoIST()}T12:00:00Z`) || todayIsoIST()}>
          {loading ? <p className="admin-muted">Loading…</p> : null}
          {!loading ? (
            <>
              <div className="staff-attendance-stats">
                <div className="staff-attendance-stat">
                  <p className="staff-attendance-stat__label">Working time</p>
                  <p className="staff-attendance-stat__value">{formatDurationSeconds(liveWorkSeconds)}</p>
                </div>
                <div className="staff-attendance-stat">
                  <p className="staff-attendance-stat__label">Break time</p>
                  <p className="staff-attendance-stat__value">{formatDurationSeconds(liveBreakSeconds)}</p>
                </div>
                {attendance?.clock_in_at ? (
                  <div className="staff-attendance-stat">
                    <p className="staff-attendance-stat__label">First clock in</p>
                    <p className="staff-attendance-stat__value" style={{ fontSize: '1rem' }}>
                      {formatTimeIST(attendance.clock_in_at)}
                    </p>
                  </div>
                ) : null}
              </div>

              <div className="staff-attendance-actions">
                {!isClockedIn && !isPaused ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary"
                    disabled={!!busy}
                    onClick={() => runAction('clock-in', clockInStaff)}
                  >
                    {canClockInAgain ? 'Clock in again' : 'Clock in'}
                  </button>
                ) : null}
                {isClockedIn ? (
                  <>
                    <button
                      type="button"
                      className="admin-btn admin-btn--secondary"
                      disabled={!!busy}
                      onClick={() => runAction('pause', pauseStaffAttendance)}
                    >
                      Pause
                    </button>
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary"
                      disabled={!!busy}
                      onClick={() => runAction('clock-out', () => clockOutStaff(workSummary))}
                    >
                      Clock out
                    </button>
                  </>
                ) : null}
                {isPaused ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary"
                    disabled={!!busy}
                    onClick={() => runAction('resume', resumeStaffAttendance)}
                  >
                    Resume
                  </button>
                ) : null}
              </div>

              {(isClockedIn || isPaused || hasSessionToday) ? (
                <div className="staff-attendance-log">
                  <label className="admin-filter-field">
                    <span className="admin-filter-field__label">What did you work on today?</span>
                    <textarea
                      className="admin-input"
                      value={workSummary}
                      onChange={(e) => setWorkSummary(e.target.value)}
                      placeholder="A few words about your tasks today…"
                    />
                  </label>
                  <div className="admin-btn-group" style={{ marginTop: 10 }}>
                    <button
                      type="button"
                      className="admin-btn admin-btn--secondary admin-btn--sm"
                      disabled={!!busy || !workSummary.trim()}
                      onClick={() => runAction('save-summary', () => saveStaffWorkSummary(workSummary))}
                    >
                      Save log
                    </button>
                  </div>
                </div>
              ) : (
                <AdminEmptyState
                  title="Ready when you are"
                  description="Clock in when you begin work. You can pause for breaks and add your work log as you go."
                />
              )}

              {attendance?.status === 'AUTO_CLOSED' ? (
                <p className="admin-alert admin-alert--warn" style={{ marginTop: 12 }}>
                  Yesterday&apos;s session was auto-closed at midnight. Review your log and clock in again if needed.
                </p>
              ) : null}
            </>
          ) : null}
        </AdminPanel>
      ) : null}

      {mode === 'forgot' ? (
        <AdminPanel title="Forgot to log" subtitle="For today or yesterday — not available on approved leave days.">
          <form onSubmit={handleForgotSubmit} className="staff-attendance-edit-grid">
            <label className="admin-filter-field">
              <span className="admin-filter-field__label">Date</span>
              <input
                type="date"
                className="admin-input"
                value={forgotForm.work_date}
                onChange={(e) => setForgotForm((f) => ({ ...f, work_date: e.target.value }))}
                required
              />
            </label>
            <label className="admin-filter-field">
              <span className="admin-filter-field__label">Start time</span>
              <input
                type="time"
                className="admin-input"
                value={forgotForm.start_time}
                onChange={(e) => setForgotForm((f) => ({ ...f, start_time: e.target.value }))}
                required
              />
            </label>
            <label className="admin-filter-field">
              <span className="admin-filter-field__label">End time</span>
              <input
                type="time"
                className="admin-input"
                value={forgotForm.end_time}
                onChange={(e) => setForgotForm((f) => ({ ...f, end_time: e.target.value }))}
                required
              />
            </label>
            <label className="admin-filter-field" style={{ gridColumn: '1 / -1' }}>
              <span className="admin-filter-field__label">What did you work on?</span>
              <textarea
                className="admin-input"
                value={forgotForm.work_summary}
                onChange={(e) => setForgotForm((f) => ({ ...f, work_summary: e.target.value }))}
                required
                minLength={3}
              />
            </label>
            <label className="admin-filter-field" style={{ gridColumn: '1 / -1' }}>
              <span className="admin-filter-field__label">Reason for late log</span>
              <textarea
                className="admin-input"
                value={forgotForm.reason}
                onChange={(e) => setForgotForm((f) => ({ ...f, reason: e.target.value }))}
                required
                minLength={3}
              />
            </label>
            <div style={{ gridColumn: '1 / -1' }}>
              <button type="submit" className="admin-btn admin-btn--primary" disabled={busy === 'forgot'}>
                Save late log
              </button>
            </div>
          </form>
        </AdminPanel>
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
