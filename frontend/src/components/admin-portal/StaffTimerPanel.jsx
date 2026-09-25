import { useCallback, useEffect, useMemo, useState } from 'react'
import { formatDateIN, formatTimeIST, todayIsoIST } from '../../lib/datetime.js'
import {
  clockInStaff,
  clockOutStaff,
  fetchTodayAttendance,
  formatDurationSeconds,
  pauseStaffAttendance,
  resumeStaffAttendance,
  saveStaffWorkSummary,
} from '../../lib/staffAttendanceApi.js'
import { AdminPanel } from './ui/index.js'
import './staff-attendance.css'

export function StaffTimerPanel({ title = "Today's session", subtitle }) {
  const [todayState, setTodayState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [workSummary, setWorkSummary] = useState('')
  const [tick, setTick] = useState(0)

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

  useEffect(() => {
    loadToday()
  }, [loadToday])

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

  return (
    <>
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

      <AdminPanel
        title={title}
        subtitle={subtitle || formatDateIN(`${todayIsoIST()}T12:00:00Z`) || todayIsoIST()}
      >
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
              {!hasSessionToday || canClockInAgain ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary"
                  disabled={!!busy}
                  onClick={() => runAction('clock-in', clockInStaff)}
                >
                  {busy === 'clock-in' ? 'Starting…' : 'Clock in'}
                </button>
              ) : null}
              {isClockedIn ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--secondary"
                  disabled={!!busy}
                  onClick={() => runAction('pause', pauseStaffAttendance)}
                >
                  {busy === 'pause' ? 'Pausing…' : 'Pause break'}
                </button>
              ) : null}
              {isPaused ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--secondary"
                  disabled={!!busy}
                  onClick={() => runAction('resume', resumeStaffAttendance)}
                >
                  {busy === 'resume' ? 'Resuming…' : 'Resume work'}
                </button>
              ) : null}
              {isClockedIn || isPaused ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost"
                  disabled={!!busy}
                  onClick={() => runAction('clock-out', () => clockOutStaff(workSummary))}
                >
                  {busy === 'clock-out' ? 'Clocking out…' : 'Clock out'}
                </button>
              ) : null}
            </div>

            {(isClockedIn || isPaused || hasSessionToday) && (
              <div className="staff-attendance-log" style={{ marginTop: 16 }}>
                <label className="admin-filter-field">
                  <span className="admin-filter-field__label">What are you working on?</span>
                  <textarea
                    className="admin-input"
                    value={workSummary}
                    onChange={(e) => setWorkSummary(e.target.value)}
                    placeholder="Brief note on today&apos;s work…"
                  />
                </label>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  style={{ marginTop: 8 }}
                  disabled={!!busy || !workSummary.trim()}
                  onClick={() => runAction('summary', () => saveStaffWorkSummary(workSummary.trim()))}
                >
                  {busy === 'summary' ? 'Saving…' : 'Save note'}
                </button>
              </div>
            )}

            {attendance?.status === 'AUTO_CLOSED' ? (
              <p className="admin-alert admin-alert--warn" style={{ marginTop: 12 }}>
                Yesterday&apos;s session was auto-closed at midnight. Clock in again when you start today.
              </p>
            ) : null}
          </>
        ) : null}
      </AdminPanel>
    </>
  )
}
