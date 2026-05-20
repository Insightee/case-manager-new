import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import {
  formatSessionTimeRange,
  isLogEditable,
  logToFormState,
  validateSessionLogForm,
} from '../../lib/sessionLogUtils.js'

const ATTENDANCE = [
  { value: 'PRESENT', label: 'Present' },
  { value: 'LATE', label: 'Late' },
  { value: 'PARTIAL', label: 'Partial' },
  { value: 'ABSENT', label: 'Absent' },
]

const FIELDS = [
  { key: 'session_notes', label: 'Session notes', hint: 'Internal — not shared with family', rows: 2 },
  { key: 'activities_done', label: 'What you did today', hint: 'Required — brief summary of the visit', rows: 3, required: true },
  { key: 'goals_addressed', label: 'Goals worked on', hint: 'IEP or treatment goals touched this session', rows: 2 },
  { key: 'observations', label: 'Clinical observations', hint: 'Internal — progress, behavior, concerns', rows: 2 },
  { key: 'follow_ups', label: 'Follow-ups', hint: 'Tasks before next visit', rows: 2 },
  {
    key: 'parent_notes',
    label: 'Update for family',
    hint: 'Shared after admin review — helps parents get a timely update',
    rows: 3,
    highlight: true,
  },
]

const emptyLogForm = {
  attendance_status: 'PRESENT',
  session_notes: '',
  activities_done: '',
  goals_addressed: '',
  observations: '',
  follow_ups: '',
  parent_notes: '',
  late_reason: '',
}

export function SubmitSessionLogForm({
  session,
  existingLog = null,
  caseCode,
  childName,
  required = false,
  onSuccess,
  onCancel,
}) {
  const isEdit = Boolean(existingLog?.id)
  const [form, setForm] = useState(emptyLogForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (existingLog) {
      setForm(logToFormState(existingLog))
    } else {
      setForm(emptyLogForm)
    }
  }, [existingLog?.id, session?.id])

  const isLateSession = useMemo(() => {
    if (!session?.scheduled_date) return false
    const today = new Date().toISOString().slice(0, 10)
    return session.scheduled_date < today
  }, [session])

  const timeRange = formatSessionTimeRange(session)
  const displayName = childName || session?.child_name || caseCode || session?.case_code || 'Client'
  const editable = !isEdit || isLogEditable(existingLog)

  async function handleSubmit(e) {
    e.preventDefault()
    const validationError = validateSessionLogForm(form, { isLateSession })
    if (validationError) {
      setError(validationError)
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const body = {
        ...form,
        late_reason: form.late_reason || undefined,
      }
      if (isEdit) {
        await apiFetch(`/api/v1/daily-logs/${existingLog.id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        })
      } else {
        await apiFetch('/api/v1/daily-logs', {
          method: 'POST',
          body: JSON.stringify({ session_id: session.id, ...body }),
        })
      }
      onSuccess?.()
    } catch (err) {
      setError(err.message || 'Could not save log')
    } finally {
      setSubmitting(false)
    }
  }

  if (isEdit && !editable) {
    return (
      <div className="ic-session-log-panel ic-session-log-panel--locked">
        <p className="ic-session-log-panel__locked-title">Editing closed</p>
        <p className="ic-session-log-panel__locked-copy">
          This log was submitted more than 24 hours ago or has already been reviewed. Contact your case manager if you
          need a correction.
        </p>
        {onCancel ? (
          <button type="button" className="ic-btn ic-btn--ghost" onClick={onCancel}>
            Close
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <div className={`ic-session-log-panel${required ? ' ic-session-log-panel--required' : ''}`}>
      <header className="ic-session-log-panel__head">
        <div>
          <p className="ic-session-log-panel__eyebrow">
            {isEdit ? 'Edit session log' : required ? 'Required to close session' : 'Session log'}
          </p>
          <h2 className="ic-session-log-panel__title">
            {isEdit ? 'Update visit details' : 'Complete session log'}
          </h2>
          <p className="ic-session-log-panel__meta">
            <strong>{displayName}</strong>
            {session?.scheduled_date ? <> · {session.scheduled_date}</> : null}
            {timeRange ? <> · {timeRange}</> : null}
          </p>
        </div>
        {!required && onCancel ? (
          <button type="button" className="ic-btn ic-btn--ghost ic-session-log-panel__dismiss" onClick={onCancel}>
            Close
          </button>
        ) : null}
      </header>

      {required ? (
        <p className="ic-session-log-panel__banner">
          Your timer has stopped. Submit this log now so the visit is recorded and the family can get an update after
          admin review. You can edit for <strong>24 hours</strong> if you need to fix something.
        </p>
      ) : isEdit ? (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          Changes save while the log is still pending review and within 24 hours of submission.
        </p>
      ) : (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          Capture what happened while it is fresh. Family-facing notes are shared after admin review.
        </p>
      )}

      {error ? <p className="ic-session-log-panel__error">{error}</p> : null}

      <form className="ic-session-log-form" onSubmit={handleSubmit}>
        <fieldset className="ic-session-log-form__attendance">
          <legend>Attendance</legend>
          <div className="ic-session-log-form__attendance-options">
            {ATTENDANCE.map((a) => (
              <label key={a.value} className="ic-session-log-attendance">
                <input
                  type="radio"
                  name="attendance"
                  value={a.value}
                  checked={form.attendance_status === a.value}
                  onChange={() => setForm({ ...form, attendance_status: a.value })}
                />
                <span>{a.label}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="ic-session-log-form__grid">
          {FIELDS.map(({ key, label, hint, rows, highlight, required: fieldRequired }) => (
            <label
              key={key}
              className={`ic-session-log-field${highlight ? ' ic-session-log-field--highlight' : ''}`}
            >
              <span className="ic-session-log-field__label">
                {label}
                {fieldRequired ? <span className="ic-session-log-field__req">Required</span> : null}
              </span>
              <span className="ic-session-log-field__hint">{hint}</span>
              <textarea
                value={form[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                rows={rows}
                required={fieldRequired}
              />
            </label>
          ))}
        </div>

        {isLateSession ? (
          <label className="ic-session-log-field ic-session-log-field--warn">
            <span className="ic-session-log-field__label">
              Late reason
              <span className="ic-session-log-field__req">Required</span>
            </span>
            <span className="ic-session-log-field__hint">This session is from a past day — explain for admin review</span>
            <textarea
              required
              value={form.late_reason}
              onChange={(e) => setForm({ ...form, late_reason: e.target.value })}
              rows={2}
            />
          </label>
        ) : null}

        <div className="ic-session-log-form__actions">
          <button type="submit" className="ic-btn ic-btn--primary ic-session-log-form__submit" disabled={submitting}>
            {submitting ? 'Saving…' : isEdit ? 'Save changes' : 'Submit log & close session'}
          </button>
          {required && onCancel ? (
            <button type="button" className="ic-btn ic-btn--ghost" onClick={onCancel}>
              Finish later
            </button>
          ) : null}
          {!required && onCancel ? (
            <button type="button" className="ic-btn ic-btn--ghost" onClick={onCancel}>
              Cancel
            </button>
          ) : null}
        </div>
        {required ? (
          <p className="ic-session-log-form__footnote">
            “Finish later” keeps this visit in <strong>Needs log</strong> until you submit.
          </p>
        ) : null}
      </form>
    </div>
  )
}
