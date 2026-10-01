import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { formatDateIN, formatTimeIST, todayIsoIST } from '../../lib/datetime.js'
import {
  clockInStaff,
  clockOutStaff,
  fetchTodayAttendance,
  formatDurationSeconds,
  saveStaffWorkSummary,
} from '../../lib/staffAttendanceApi.js'
import { AdminPanel } from './ui/index.js'
import './staff-attendance.css'

export function StaffTimerPanel({ title = "Today's session", subtitle, className = '' }) {
  const [todayState, setTodayState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [workSummary, setWorkSummary] = useState('')
  const [tick, setTick] = useState(0)
  const syncRef = useRef({ at: Date.now(), seconds: 0 })

  const loadToday = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchTodayAttendance()
      setTodayState(data)
      setWorkSummary(data?.attendance?.work_summary || '')
      syncRef.current = {
        at: Date.now(),
        seconds: data?.attendance?.total_work_seconds || 0,
      }
    } catch (err) {
      setError(err.message || 'Could not load attendance for today.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadToday()
  }, [loadToday])

  const isClockedIn = Boolean(todayState?.is_clocked_in)
  const attendance = todayState?.attendance
  const hasSessionToday = Boolean(attendance)
  const canClockIn =
    !isClockedIn
    && (!hasSessionToday || attendance?.status === 'COMPLETED' || attendance?.status === 'AUTO_CLOSED')

  useEffect(() => {
    if (!isClockedIn) return undefined
    const id = window.setInterval(() => setTick((t) => t + 1), 1000)
    return () => window.clearInterval(id)
  }, [isClockedIn])

  const liveTotalSeconds = useMemo(() => {
    void tick
    if (!attendance) return 0
    if (!isClockedIn) return attendance.total_work_seconds || 0
    const elapsed = Math.floor((Date.now() - syncRef.current.at) / 1000)
    return (syncRef.current.seconds || 0) + Math.max(0, elapsed)
  }, [attendance, isClockedIn, tick])

  const startTimeLabel = useMemo(() => {
    if (!attendance) return '—'
    const raw = attendance.session_start_at || attendance.clock_in_at
    return raw ? formatTimeIST(raw) : '—'
  }, [attendance])

  const endTimeLabel = useMemo(() => {
    if (!attendance || isClockedIn) return '—'
    return attendance.clock_out_at ? formatTimeIST(attendance.clock_out_at) : '—'
  }, [attendance, isClockedIn])

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
    <div className={`staff-timer-panel ${className}`.trim()}>
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
            {isClockedIn ? (
              <p className="staff-timer-panel__live" aria-live="polite">
                <span className="staff-timer-panel__live-dot" aria-hidden />
                {formatDurationSeconds(liveTotalSeconds)} elapsed
              </p>
            ) : null}

            <div className="staff-attendance-stats staff-attendance-stats--timer">
              <div className="staff-attendance-stat">
                <p className="staff-attendance-stat__label">Start time</p>
                <p className="staff-attendance-stat__value staff-attendance-stat__value--time">{startTimeLabel}</p>
              </div>
              <div className="staff-attendance-stat">
                <p className="staff-attendance-stat__label">End time</p>
                <p className="staff-attendance-stat__value staff-attendance-stat__value--time">{endTimeLabel}</p>
              </div>
              <div className="staff-attendance-stat">
                <p className="staff-attendance-stat__label">Total time</p>
                <p className="staff-attendance-stat__value">{formatDurationSeconds(liveTotalSeconds)}</p>
              </div>
            </div>

            <div className="staff-attendance-actions">
              {canClockIn ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary"
                  disabled={!!busy}
                  onClick={() => runAction('clock-in', clockInStaff)}
                >
                  {busy === 'clock-in' ? 'Starting…' : hasSessionToday ? 'Clock in again' : 'Clock in'}
                </button>
              ) : null}
              {isClockedIn ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary"
                  disabled={!!busy}
                  onClick={() => runAction('clock-out', () => clockOutStaff(workSummary))}
                >
                  {busy === 'clock-out' ? 'Clocking out…' : 'Clock out'}
                </button>
              ) : null}
            </div>

            {(isClockedIn || hasSessionToday) && (
              <div className="staff-attendance-log">
                <label className="admin-filter-field">
                  <span className="admin-filter-field__label">What are you working on?</span>
                  <textarea
                    className="admin-input"
                    value={workSummary}
                    onChange={(e) => setWorkSummary(e.target.value)}
                    placeholder="Brief note on today's work…"
                  />
                </label>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  disabled={!!busy || !workSummary.trim()}
                  onClick={() => runAction('summary', () => saveStaffWorkSummary(workSummary.trim()))}
                >
                  {busy === 'summary' ? 'Saving…' : 'Save note'}
                </button>
              </div>
            )}

            {attendance?.status === 'AUTO_CLOSED' && !isClockedIn ? (
              <p className="admin-alert admin-alert--warn staff-timer-panel__notice">
                Yesterday&apos;s session was auto-closed at midnight. Clock in again when you start today.
              </p>
            ) : null}
          </>
        ) : null}
      </AdminPanel>
    </div>
  )
}
