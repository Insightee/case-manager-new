import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { formatDisplayDate, formatTimeIN12, parseApiDatetime } from '../../../lib/datetime.js'
import {
  canEditSessionTimes,
  effectiveDurationMins,
  formatEditedRange,
  formatScheduledRange,
} from '../../../lib/sessionTimes.js'
import { sessionLogProgressPct } from '../../../lib/clinicalScoring.js'

function toDatetimeLocalValue(iso) {
  const d = parseApiDatetime(iso)
  if (!d) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function correctedDurationMins(startLocal, endLocal) {
  if (!startLocal || !endLocal) return null
  const start = new Date(startLocal)
  const end = new Date(endLocal)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null
  const mins = Math.round((end.getTime() - start.getTime()) / 60000)
  return mins > 0 ? mins : null
}

function wallClock(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

function actualClock(iso) {
  if (!iso) return null
  return formatTimeIN12(iso, { suffix: '' })
}

export function SessionLogV2Chrome({
  session,
  caseCode,
  childName,
  sessionEvidence,
  log,
  onTimesUpdated,
}) {
  const [hasIep, setHasIep] = useState(false)
  const [editing, setEditing] = useState(false)
  const [startLocal, setStartLocal] = useState('')
  const [endLocal, setEndLocal] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const displayName = childName || session?.child_name || 'Client'
  const code = caseCode || session?.case_code || ''
  const progress = sessionLogProgressPct(sessionEvidence?.goals || [])
  const duration = effectiveDurationMins(session, log)
  const editedClock = formatEditedRange(session)
  const scheduled = formatScheduledRange(session)
  const canEdit = canEditSessionTimes(session, log)
  const scheduledStart = wallClock(session?.start_time)
  const scheduledEnd = wallClock(session?.end_time)
  const loginAt = actualClock(session?.edited_start_at || session?.actual_start_at)
  const logoutAt = session?.edited_end_at || session?.actual_end_at ? actualClock(session?.edited_end_at || session?.actual_end_at) : null
  const sessionActive = session?.status === 'IN_PROGRESS'

  useEffect(() => {
    if (!session?.case_id) return
    let cancelled = false
    apiFetch(`/api/v1/cases/${session.case_id}/iep-plan`)
      .then(() => {
        if (!cancelled) setHasIep(true)
      })
      .catch(() => {
        if (!cancelled) setHasIep(false)
      })
    return () => {
      cancelled = true
    }
  }, [session?.case_id])

  useEffect(() => {
    if (!editing || !session) return
    setStartLocal(toDatetimeLocalValue(session.edited_start_at || session.actual_start_at))
    setEndLocal(toDatetimeLocalValue(session.edited_end_at || session.actual_end_at))
    setReason('')
    setError('')
  }, [editing, session?.id, session?.actual_start_at, session?.actual_end_at])

  const correctedMins = useMemo(() => correctedDurationMins(startLocal, endLocal), [startLocal, endLocal])

  async function saveTimes(e) {
    e.preventDefault()
    if (!session?.id) return
    if (reason.trim().length < 5) {
      setError('Add a short reason for the time correction (at least 5 characters).')
      return
    }
    if (!correctedDurationMins(startLocal, endLocal)) {
      setError('End time must be after start time.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const updated = await apiFetch(`/api/v1/sessions/${session.id}/actual-times`, {
        method: 'PATCH',
        body: JSON.stringify({
          actual_start_at: new Date(startLocal).toISOString(),
          actual_end_at: new Date(endLocal).toISOString(),
          edit_reason: reason.trim(),
        }),
      })
      onTimesUpdated?.(updated)
      setEditing(false)
    } catch (err) {
      setError(err.message || 'Could not update times')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="sl-v2-context">
        <div>
          <p className="sl-v2-context__label">Client context</p>
          <p className="sl-v2-context__case">Case ID: {code ? `#${code}` : '—'}</p>
        </div>
        <div className="sl-v2-context__progress">
          <p className="sl-v2-context__progress-label">Progress: {progress}%</p>
          <div className="sl-v2-progress-bar" aria-hidden="true">
            <div className="sl-v2-progress-bar__fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </div>

      <div className="sl-v2-patient">
        <div>
          <h2 className="sl-v2-patient__name">{displayName}</h2>
          <p className="sl-v2-patient__meta">
            {session?.scheduled_date ? <span>{formatDisplayDate(session.scheduled_date)}</span> : null}
            {hasIep ? <span className="sl-v2-badge sl-v2-badge--iep">Active IEP</span> : null}
          </p>
          {session?.mode ? <p className="sl-v2-patient__detail">Setting: {session.mode}</p> : null}
        </div>
        <div className="sl-v2-patient__completion">
          <p className="sl-v2-patient__completion-val">{progress}%</p>
          <p className="sl-v2-context__progress-label">Session log</p>
        </div>
      </div>

      <div className="sl-v2-duration sl-v2-duration-card">
        <div className="sl-v2-duration__main">
          <p className="sl-v2-duration__label">Session duration</p>
          {scheduled ? <p className="sl-v2-duration__scheduled-line">Scheduled: {scheduled}</p> : null}

          <div className="sl-v2-duration-grid">
            <div className="sl-v2-duration-grid__col">
              <p className="sl-v2-duration-grid__heading">Scheduled</p>
              <p className="sl-v2-duration-grid__row">
                <span>Start</span>
                <strong>{scheduledStart}</strong>
              </p>
              <p className="sl-v2-duration-grid__row">
                <span>End</span>
                <strong>{scheduledEnd}</strong>
              </p>
            </div>
            <div className="sl-v2-duration-grid__col">
              <p className="sl-v2-duration-grid__heading">Actual</p>
              <p className="sl-v2-duration-grid__row">
                <span>Login</span>
                <strong>{loginAt || '—'}</strong>
              </p>
              <p className="sl-v2-duration-grid__row">
                <span>Logout</span>
                <strong>{sessionActive ? 'Not clocked out yet' : logoutAt || '—'}</strong>
              </p>
              {duration ? (
                <p className="sl-v2-duration-grid__duration">
                  Actual duration: <strong>{duration} min</strong>
                </p>
              ) : null}
            </div>
          </div>

          {editedClock && editedClock !== clock ? (
            <p className="sl-v2-duration__sub sl-v2-duration__sub--edited">
              Corrected: <strong>{editedClock}</strong>
            </p>
          ) : null}
        </div>
        {canEdit ? (
          <button type="button" className="sl-v2-duration__edit" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Close' : 'Edit times'}
          </button>
        ) : null}
      </div>

      {editing ? (
        <div className="sl-v2-time-edit">
          <p className="sl-v2-time-edit__title">Correct session times</p>
          <div className="sl-v2-time-edit__grid">
            <label className="gs-field">
              <span className="gs-field__label">Start</span>
              <input
                type="datetime-local"
                required
                value={startLocal}
                onChange={(e) => setStartLocal(e.target.value)}
              />
            </label>
            <label className="gs-field">
              <span className="gs-field__label">End</span>
              <input
                type="datetime-local"
                required
                value={endLocal}
                onChange={(e) => setEndLocal(e.target.value)}
              />
            </label>
          </div>
          {correctedMins ? (
            <p className="sl-v2-duration__sub">Corrected duration: {correctedMins} minutes</p>
          ) : null}
          <label className="gs-field">
            <span className="gs-field__label">Reason for correction</span>
            <textarea
              rows={2}
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Forgot to end timer; adjusted to match actual visit."
            />
          </label>
          {error ? <p className="gs-error">{error}</p> : null}
          <div className="sl-v2-time-edit__actions">
            <button type="button" className="gs-btn gs-btn--ghost" onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button type="button" className="gs-btn gs-btn--primary" disabled={busy} onClick={saveTimes}>
              {busy ? 'Saving…' : 'Save times'}
            </button>
          </div>
        </div>
      ) : null}
    </>
  )
}
