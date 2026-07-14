import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { parseApiDatetime } from '../../lib/datetime.js'
import { formatClockRange, formatScheduledRange } from '../../lib/sessionTimes.js'

function toDatetimeLocalValue(iso) {
  const d = parseApiDatetime(iso)
  if (!d) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function initialCorrectedStart(session) {
  return session?.edited_start_at || session?.actual_start_at
}

function initialCorrectedEnd(session) {
  return session?.edited_end_at || session?.actual_end_at
}

function correctedDurationMins(startLocal, endLocal) {
  if (!startLocal || !endLocal) return null
  const start = new Date(startLocal)
  const end = new Date(endLocal)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null
  const mins = Math.round((end.getTime() - start.getTime()) / 60000)
  return mins > 0 ? mins : null
}

function formatLocalTimePreview(local) {
  if (!local) return null
  const d = new Date(local)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

/**
 * Propose corrected clock-in/out on a completed session (24h window enforced server-side).
 */
export function EditActualTimesModal({ open, session, onClose, onSaved }) {
  const [startLocal, setStartLocal] = useState('')
  const [endLocal, setEndLocal] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !session) return
    setStartLocal(toDatetimeLocalValue(initialCorrectedStart(session)))
    setEndLocal(toDatetimeLocalValue(initialCorrectedEnd(session)))
    setReason('')
    setError('')
  }, [open, session])

  useEffect(() => {
    if (!open) return undefined
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  const displayName = session?.child_name || session?.case_code || 'Session'
  const scheduledLine = session ? formatScheduledRange(session) : null
  const clockRange = session ? formatClockRange(session) : null
  const correctedPreview =
    startLocal && endLocal
      ? [formatLocalTimePreview(startLocal), formatLocalTimePreview(endLocal)].filter(Boolean).join(' – ')
      : null
  const correctedMins = useMemo(() => correctedDurationMins(startLocal, endLocal), [startLocal, endLocal])
  const clockMins = useMemo(
    () =>
      session?.actual_start_at && session?.actual_end_at
        ? correctedDurationMins(
            toDatetimeLocalValue(session.actual_start_at),
            toDatetimeLocalValue(session.actual_end_at),
          )
        : null,
    [session],
  )
  const reasonOk = reason.trim().length >= 5
  const timesValid = correctedDurationMins(startLocal, endLocal) != null

  if (!open || !session) return null

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!reasonOk) {
      setError('Please explain why you are correcting the times (at least 5 characters).')
      return
    }
    if (!timesValid) {
      setError('End time must be after start time.')
      return
    }
    setBusy(true)
    try {
      const updated = await apiFetch(`/api/v1/sessions/${session.id}/actual-times`, {
        method: 'PATCH',
        body: JSON.stringify({
          actual_start_at: new Date(startLocal).toISOString(),
          actual_end_at: new Date(endLocal).toISOString(),
          edit_reason: reason.trim(),
        }),
      })
      onSaved?.(updated)
      onClose?.()
    } catch (err) {
      setError(err.message || 'Could not update times')
    } finally {
      setBusy(false)
    }
  }

  return createPortal(
    <div
      className="ic-case-status-modal ic-edit-times-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-times-title"
    >
      <button type="button" className="ic-case-status-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="ic-case-status-modal__sheet ic-edit-times-modal__sheet">
        <header className="ic-edit-times-modal__head">
          <div className="ic-edit-times-modal__head-text">
            <p className="ic-edit-times-modal__eyebrow">Time correction</p>
            <h2 id="edit-times-title">Correct session times</h2>
            <p className="ic-edit-times-modal__meta">
              <strong>{displayName}</strong>
              {session.scheduled_date ? <> · {formatDisplayDate(session.scheduled_date)}</> : null}
            </p>
          </div>
          <button
            type="button"
            className="ic-edit-times-modal__close"
            aria-label="Close"
            onClick={onClose}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M6 6l12 12M18 6L6 18"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </header>

        <form className="ic-case-status-modal__form ic-edit-times-modal__form" onSubmit={handleSubmit}>
          <div className="ic-edit-times-modal__body">
            <div className="ic-edit-times-modal__refs" aria-label="Session time reference">
              {scheduledLine ? (
                <div className="ic-edit-times-modal__ref">
                  <span className="ic-edit-times-modal__ref-label">Scheduled</span>
                  <span className="ic-edit-times-modal__ref-value">{scheduledLine}</span>
                </div>
              ) : null}
              {clockRange ? (
                <div className="ic-edit-times-modal__ref ic-edit-times-modal__ref--clock">
                  <span className="ic-edit-times-modal__ref-label">Clock record</span>
                  <span className="ic-edit-times-modal__ref-value">
                    {clockRange}
                    {clockMins != null ? (
                      <span className="ic-edit-times-modal__ref-dur"> · {clockMins} min</span>
                    ) : (
                      <span className="ic-edit-times-modal__ref-warn"> · Check times</span>
                    )}
                  </span>
                </div>
              ) : null}
            </div>

            <p className="ic-edit-times-modal__notice" role="note">
              Your correction is reviewed with the session log. The clock record above stays on file for audit.
            </p>

            {error ? (
              <p className="ic-alert ic-alert--error ic-edit-times-modal__error" role="alert">
                {error}
              </p>
            ) : null}

            <fieldset className="ic-edit-times-modal__fieldset">
              <legend>Corrected times</legend>
              <div className="ic-edit-times-modal__time-grid">
                <label className="ic-edit-times-modal__field">
                  <span className="ic-edit-times-modal__field-label">Start</span>
                  <input
                    type="datetime-local"
                    className="ic-edit-times-modal__input"
                    value={startLocal}
                    onChange={(e) => setStartLocal(e.target.value)}
                    required
                  />
                </label>
                <label className="ic-edit-times-modal__field">
                  <span className="ic-edit-times-modal__field-label">End</span>
                  <input
                    type="datetime-local"
                    className="ic-edit-times-modal__input"
                    value={endLocal}
                    onChange={(e) => setEndLocal(e.target.value)}
                    required
                  />
                </label>
              </div>
              {correctedPreview ? (
                <p className="ic-edit-times-modal__preview" aria-live="polite">
                  <span className="ic-edit-times-modal__preview-label">Correction preview</span>
                  <span className="ic-edit-times-modal__preview-value">
                    {correctedPreview} IST
                    {correctedMins != null ? (
                      <span className="ic-edit-times-modal__preview-dur"> · {correctedMins} min</span>
                    ) : (
                      <span className="ic-edit-times-modal__preview-warn"> · End must be after start</span>
                    )}
                  </span>
                </p>
              ) : null}
            </fieldset>

            <label className="ic-edit-times-modal__field ic-edit-times-modal__field--full">
              <span className="ic-edit-times-modal__field-label">
                Why are you correcting?
                <span className={`ic-edit-times-modal__char-hint${reasonOk ? ' is-ok' : ''}`}>
                  {reason.trim().length}/5 min
                </span>
              </span>
              <textarea
                className="ic-edit-times-modal__textarea"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                placeholder="e.g. Forgot to clock out, ended visit at client's door"
                required
                minLength={5}
                aria-describedby="edit-times-reason-hint"
              />
              <span id="edit-times-reason-hint" className="ic-edit-times-modal__field-hint">
                Admin needs a short note before approving the corrected times.
              </span>
            </label>
          </div>

          <div className="ic-case-status-modal__actions ic-edit-times-modal__footer">
            <button type="button" className="ic-btn ic-btn--ghost" onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button
              type="submit"
              className="ic-btn ic-btn--primary"
              disabled={busy || !reasonOk || !timesValid}
            >
              {busy ? 'Saving…' : 'Submit correction'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
