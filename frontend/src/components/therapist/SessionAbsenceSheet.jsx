import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate, formatDisplayDateTimeRange, todayIsoIST } from '../../lib/datetime.js'
import { isBackfillWindowActive, migrationBackfillDateBounds } from '../../lib/leaveMigration.js'
import { logsPathForSession } from '../../lib/sessionStartRules.js'

function sliceTime(t) {
  if (!t) return ''
  return String(t).slice(0, 5)
}

/** Log child absent — today via scheduled visit; July backfill via date picker + optional auto-session. */
export function SessionAbsenceSheet({
  sessions = [],
  selectedSessionId,
  onSessionChange,
  onSuccess,
  onError,
  disabled = false,
  caseId = null,
  migrationInfo = null,
}) {
  const [reason, setReason] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')
  const [pendingRequest, setPendingRequest] = useState(null)
  const [statusLoading, setStatusLoading] = useState(false)

  const backfillActive = isBackfillWindowActive(migrationInfo)
  const dateBounds = useMemo(() => migrationBackfillDateBounds(migrationInfo), [migrationInfo])
  const today = todayIsoIST()
  const [absenceDate, setAbsenceDate] = useState(today)

  const sessionId = selectedSessionId || (sessions[0]?.id ?? null)
  const session = sessions.find((s) => s.id === sessionId) || sessions[0]
  const sessionsForSelectedDate = useMemo(() => {
    if (!caseId) return sessions
    return sessions.filter((s) => s.case_id === caseId && s.scheduled_date === absenceDate)
  }, [sessions, caseId, absenceDate])

  const activeSessionId = sessionsForSelectedDate[0]?.id ?? sessionId
  const activeSession = sessionsForSelectedDate[0] || session
  const liveSession = String(activeSession?.status || '').toUpperCase() === 'IN_PROGRESS'

  useEffect(() => {
    if (backfillActive && dateBounds?.min) {
      setAbsenceDate((prev) => {
        if (prev >= dateBounds.min && prev <= today) return prev
        return today
      })
    }
  }, [backfillActive, dateBounds?.min, today])

  useEffect(() => {
    if (!activeSession) {
      if (!backfillActive) setStartTime('')
      if (!backfillActive) setEndTime('')
      return
    }
    setStartTime(sliceTime(activeSession.start_time))
    setEndTime(sliceTime(activeSession.end_time))
  }, [activeSession?.id, activeSession?.start_time, activeSession?.end_time, backfillActive])

  useEffect(() => {
    if (!activeSessionId || backfillActive) {
      if (backfillActive) setPendingRequest(null)
      return
    }
    let cancelled = false
    setStatusLoading(true)
    apiFetch(`/api/v1/sessions/${activeSessionId}/absence`)
      .then((data) => {
        if (cancelled) return
        if (data?.status === 'pending' && data.absence_request) {
          setPendingRequest(data.absence_request)
        } else if (data?.status === 'approved' && data.absence_request) {
          setPendingRequest({ ...data.absence_request, _approved: true })
        } else {
          setPendingRequest(null)
        }
      })
      .catch(() => {
        if (!cancelled) setPendingRequest(null)
      })
      .finally(() => {
        if (!cancelled) setStatusLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [activeSessionId, backfillActive])

  async function patchSessionTimesIfNeeded() {
    if (!activeSessionId || !activeSession || backfillActive) return
    const nextStart = startTime || null
    const nextEnd = endTime || null
    const prevStart = sliceTime(activeSession.start_time) || null
    const prevEnd = sliceTime(activeSession.end_time) || null
    if (nextStart === prevStart && nextEnd === prevEnd) return
    await apiFetch(`/api/v1/sessions/${activeSessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        start_time: nextStart,
        end_time: nextEnd,
      }),
    })
  }

  async function submitChildAbsent(e) {
    e.preventDefault()
    if (busy) return
    if (backfillActive) {
      if (!caseId) {
        setLocalError('Choose a client first.')
        return
      }
      if (!absenceDate) {
        setLocalError('Choose the date the child was absent.')
        return
      }
    } else if (!activeSessionId) {
      setLocalError('Choose a scheduled visit for today.')
      return
    }

    setBusy(true)
    setLocalError('')
    try {
      if (backfillActive) {
        const created = await apiFetch('/api/v1/sessions/child-absence/backfill', {
          method: 'POST',
          body: JSON.stringify({
            case_id: Number(caseId),
            scheduled_date: absenceDate,
            reason: reason.trim() || null,
            start_time: startTime || null,
            end_time: endTime || null,
          }),
        })
        setReason('')
        if (created) setPendingRequest(created)
        onSuccess?.('Child absent logged — parent or admin will review.', activeSessionId)
        return
      }

      await patchSessionTimesIfNeeded()
      const created = await apiFetch(`/api/v1/sessions/${activeSessionId}/absence`, {
        method: 'POST',
        body: JSON.stringify({
          absence_type: 'CLIENT_ABSENT',
          reason: reason.trim() || null,
        }),
      })
      setReason('')
      if (created) setPendingRequest(created)
      onSuccess?.('Child absent logged — parent or admin will review.', activeSessionId)
    } catch (err) {
      if (err.status === 409 && err.detail?.existing && err.detail?.absence_request) {
        setPendingRequest(err.detail.absence_request)
        onSuccess?.(err.detail.message || 'Child absence already submitted for this session.', activeSessionId)
        return
      }
      const msg = err.message || 'Could not submit child absent'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  if (!backfillActive && !sessions.length) {
    return (
      <div className="ic-session-composer__absence-empty" style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p className="ic-session-composer__hint" style={{ fontWeight: 600, color: '#374151' }}>
          No session scheduled for today
        </p>
        <p className="ic-session-composer__hint">
          Child absence can only be logged against a scheduled visit. Schedule a session for today first, then come back
          here to mark the child as absent.
        </p>
        <Link
          to="/therapist/slots"
          className="ic-btn ic-btn--primary"
          style={{ textAlign: 'center', textDecoration: 'none', display: 'block' }}
        >
          Go to scheduling
        </Link>
        <p className="ic-session-composer__hint" style={{ fontSize: '0.8rem', color: '#6b7280' }}>
          Tip: If the child is absent on a day that wasn&apos;t originally scheduled, add a manual session first, then log
          the absence.
        </p>
      </div>
    )
  }

  return (
    <div className="ic-session-composer__absence">
      {backfillActive ? (
        <label className="ic-session-composer__field" style={{ marginTop: 12 }}>
          <span>Date child was absent</span>
          <input
            type="date"
            value={absenceDate}
            min={dateBounds?.min || undefined}
            max={today}
            onChange={(e) => setAbsenceDate(e.target.value)}
            className="ic-session-composer__input"
            disabled={disabled || busy}
          />
          <p className="ic-session-composer__hint" style={{ marginTop: 6 }}>
            Pick any day in July up to today — no scheduled visit required.
          </p>
        </label>
      ) : null}

      {!backfillActive && sessions.length > 1 ? (
        <label className="ic-session-composer__field" style={{ marginTop: 12 }}>
          <span>Today&apos;s visit</span>
          <select
            value={activeSessionId || ''}
            onChange={(e) => onSessionChange?.(Number(e.target.value))}
            className="ic-session-composer__input"
            disabled={disabled || busy}
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {formatDisplayDateTimeRange(s.scheduled_date, s.start_time, s.end_time)}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      {liveSession && !pendingRequest ? (
        <div
          className="ic-session-composer__status-card"
          style={{
            marginTop: 12,
            padding: 12,
            borderRadius: 8,
            border: '1px solid #93c5fd',
            background: '#eff6ff',
          }}
        >
          <p style={{ margin: 0, fontWeight: 600, color: '#1d4ed8' }}>A session is already in progress</p>
          <p style={{ margin: '6px 0 12px', fontSize: '0.875rem' }}>
            End that session before logging child absence, or continue it from session logs.
          </p>
          <Link to={logsPathForSession(activeSessionId)} className="ic-btn ic-btn--primary">
            Continue session
          </Link>
        </div>
      ) : null}

      {statusLoading ? (
        <p className="ic-session-composer__hint">Checking absence status…</p>
      ) : pendingRequest ? (
        <div
          className="ic-session-composer__status-card"
          style={{
            marginTop: 12,
            padding: 12,
            borderRadius: 8,
            border: '1px solid #fcd34d',
            background: '#fffbeb',
          }}
        >
          <p style={{ margin: 0, fontWeight: 600, color: '#b45309' }}>
            {pendingRequest._approved ? 'Child absence approved' : 'Child absence pending review'}
          </p>
          <p style={{ margin: '6px 0 0', fontSize: '0.875rem' }}>
            Submitted for {formatDisplayDate(activeSession?.scheduled_date || absenceDate)}
            {pendingRequest.reason ? ` — ${pendingRequest.reason}` : ''}
          </p>
        </div>
      ) : null}

      <div className="ic-session-composer__visit-meta">
        {activeSession?.child_name ? (
          <div className="ic-session-composer__visit-row">
            <span className="ic-session-composer__visit-label">Client</span>
            <strong>{activeSession.child_name}</strong>
          </div>
        ) : null}
        <div className="ic-session-composer__visit-row">
          <span className="ic-session-composer__visit-label">Session date</span>
          <strong>{formatDisplayDate(activeSession?.scheduled_date || absenceDate)}</strong>
        </div>
        {!pendingRequest && !liveSession ? (
          <div className="ic-session-composer__time-grid">
            <label className="ic-session-composer__field">
              <span>Start time</span>
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="ic-session-composer__input"
                disabled={disabled || busy}
              />
            </label>
            <label className="ic-session-composer__field">
              <span>End time</span>
              <input
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="ic-session-composer__input"
                disabled={disabled || busy}
              />
            </label>
          </div>
        ) : null}
      </div>

      {!pendingRequest && !liveSession ? (
        <form
          onSubmit={submitChildAbsent}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            marginTop: 12,
            position: 'sticky',
            bottom: 0,
            paddingBottom: 'max(12px, env(safe-area-inset-bottom))',
            background: 'var(--ic-surface, #fff)',
          }}
        >
          <label className="ic-session-composer__field">
            <span>Reason</span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="ic-session-composer__input"
              rows={3}
              placeholder="e.g. unwell, family travel — shown on the log as child absent"
              disabled={disabled || busy}
            />
          </label>
          {localError ? <p className="ic-session-composer__error">{localError}</p> : null}
          <p className="ic-session-composer__hint">Parent or admin must approve before billing is updated.</p>
          <p className="ic-session-composer__hint">
            For your own leave, use the{' '}
            <Link to="/therapist/leave?new=1" className="therapist-leave-page__link-btn">
              Leave tab
            </Link>
            .
          </p>
          <button type="submit" className="ic-btn ic-btn--primary ic-session-composer__submit" disabled={disabled || busy}>
            {busy ? 'Submitting…' : 'Log child absent'}
          </button>
        </form>
      ) : null}
    </div>
  )
}
