import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatApiDateIN, todayIsoIST } from '../../lib/datetime.js'
import { unwrapList } from '../../lib/listApi.js'
import { ExistingSessionForDateCard } from './ExistingSessionForDateCard.jsx'

const DURATION_PRESETS = [
  { label: '30 min', minutes: 30 },
  { label: '45 min', minutes: 45 },
  { label: '1 hour', minutes: 60 },
  { label: '1.5 hours', minutes: 90 },
]

function pad2(n) {
  return String(n).padStart(2, '0')
}

function toTimeInput(date) {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

export function defaultForgotSession() {
  const end = new Date()
  end.setMinutes(Math.floor(end.getMinutes() / 15) * 15, 0, 0)
  const start = new Date(end)
  start.setMinutes(start.getMinutes() - 60)
  return {
    case_id: '',
    session_date: todayIsoIST(),
    start_time: toTimeInput(start),
    end_time: toTimeInput(end),
  }
}

/** Map case service_location_type to API SessionMode (location is set on the case). */
export function sessionModeFromCase(caseRow) {
  const raw = caseRow?.service_location_type
  if (!raw) return 'HOME'
  const key = String(raw).toUpperCase()
  if (key === 'CLINIC') return 'CENTER'
  if (key === 'COMMUNITY') return 'HOME'
  if (['HOME', 'SCHOOL', 'CENTER', 'ONLINE'].includes(key)) return key
  return 'HOME'
}

export function combineDateAndTime(dateStr, timeStr) {
  if (!dateStr || !timeStr) return null
  const [y, m, d] = dateStr.split('-').map(Number)
  const [hh, mm] = timeStr.split(':').map(Number)
  return new Date(y, m - 1, d, hh, mm, 0, 0)
}

function formatDurationLabel(start, end) {
  if (!start || !end || end <= start) return null
  const mins = Math.round((end - start) / 60000)
  if (mins < 60) return `${mins} minutes`
  const h = Math.floor(mins / 60)
  const rem = mins % 60
  return rem ? `${h} hr ${rem} min` : `${h} hour${h > 1 ? 's' : ''}`
}

function formatDisplayDate(dateStr) {
  return formatApiDateIN(dateStr) || dateStr || ''
}

export function ForgotSessionForm({
  fallbackCases = [],
  onSubmit,
  onCancel,
  submitting,
  initialCaseId = '',
  existingSessionConflict = null,
  onExistingSessionAction,
  onDismissExistingSessionConflict,
}) {
  const [form, setForm] = useState(() => ({
    ...defaultForgotSession(),
    case_id: initialCaseId ? String(initialCaseId) : '',
  }))
  const [cases, setCases] = useState([])
  const [localError, setLocalError] = useState('')
  const [selectedPresetMinutes, setSelectedPresetMinutes] = useState(null)

  useEffect(() => {
    apiFetch('/api/v1/cases?assigned=true&page_size=100')
      .then((data) => setCases(unwrapList(data)))
      .catch(() => setCases([]))
  }, [])

  const caseOptions = useMemo(() => {
    const map = new Map()
    for (const c of cases) {
      map.set(c.id, {
        case_id: c.id,
        child_name: c.child_name || c.child?.full_name,
        case_code: c.case_code,
      })
    }
    for (const s of fallbackCases) {
      if (!map.has(s.case_id)) {
        map.set(s.case_id, { case_id: s.case_id, child_name: s.child_name, case_code: s.case_code })
      }
    }
    return [...map.values()]
  }, [cases, fallbackCases])

  const today = todayIsoIST()
  const startDt = combineDateAndTime(form.session_date, form.start_time)
  const endDt = combineDateAndTime(form.session_date, form.end_time)
  const durationLabel = formatDurationLabel(startDt, endDt)
  const isPastDay = form.session_date < today
  const isToday = form.session_date === today

  function setStartTime(time) {
    setSelectedPresetMinutes(null)
    setForm((f) => ({ ...f, start_time: time }))
  }

  function applyDurationPreset(minutes) {
    if (!form.start_time) return
    const start = combineDateAndTime(form.session_date, form.start_time)
    if (!start) return
    const end = new Date(start.getTime() + minutes * 60000)
    setSelectedPresetMinutes(minutes)
    setForm((f) => ({ ...f, end_time: toTimeInput(end) }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    setLocalError('')
    const start = combineDateAndTime(form.session_date, form.start_time)
    const end = combineDateAndTime(form.session_date, form.end_time)
    if (!start || !end) {
      setLocalError('Enter start and end times.')
      return
    }
    if (end <= start) {
      setLocalError('End time must be after start time.')
      return
    }
    if (form.session_date > today) {
      setLocalError('Session date cannot be in the future.')
      return
    }
    if (isToday && end > new Date()) {
      setLocalError('End time cannot be in the future for today.')
      return
    }
    if (!form.case_id) {
      setLocalError('Select a client.')
      return
    }
    const caseRow = cases.find((c) => c.id === Number(form.case_id))
    onSubmit({
      case_id: Number(form.case_id),
      scheduled_date: form.session_date,
      actual_start_at: start.toISOString(),
      actual_end_at: end.toISOString(),
      mode: sessionModeFromCase(caseRow),
      isPastDay,
    })
  }

  if (existingSessionConflict) {
    return (
      <ExistingSessionForDateCard
        conflict={existingSessionConflict}
        onAction={onExistingSessionAction}
        onDismiss={onDismissExistingSessionConflict}
      />
    )
  }

  return (
    <form onSubmit={handleSubmit} className="sl-composer-panel forgot-session-form">
      <header className="sl-composer-panel__head">
        <div>
          <h4 className="sl-composer-panel__title">Log a session you missed</h4>
          <p className="sl-composer-panel__subtitle">
            Pick the visit date, then enter when the session started and ended. No live timer needed.
          </p>
        </div>
        {onCancel ? (
          <button type="button" className="sl-composer-panel__close" onClick={onCancel} aria-label="Close">
            ×
          </button>
        ) : null}
      </header>

      <div className="sl-composer-panel__body">
        {!initialCaseId ? (
          <label className="sl-composer-panel__field">
            <span>Client</span>
            <select
              required
              value={form.case_id}
              onChange={(e) => setForm({ ...form, case_id: e.target.value })}
            >
              <option value="">Choose client…</option>
              {caseOptions.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.child_name || c.case_code}
                  {c.case_code && c.child_name ? ` · ${c.case_code}` : ''}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className="sl-composer-panel__client-name">
            {caseOptions.find((c) => String(c.case_id) === String(initialCaseId))?.child_name
              || caseOptions[0]?.child_name
              || caseOptions[0]?.case_code
              || 'Selected client'}
          </p>
        )}

        <label className="sl-composer-panel__field">
          <span>Session date</span>
          <input
            type="date"
            required
            max={today}
            value={form.session_date}
            onChange={(e) => setForm({ ...form, session_date: e.target.value })}
          />
          <span className="sl-composer-panel__field-hint">
            {formatDisplayDate(form.session_date)}
            {isToday ? ' · Today (IST)' : isPastDay ? ' · Past date' : ''}
          </span>
        </label>

        <div className="sl-composer-panel__grid">
          <label className="sl-composer-panel__field">
            <span>Start time</span>
            <input
              type="time"
              required
              value={form.start_time}
              onChange={(e) => setStartTime(e.target.value)}
            />
          </label>
          <label className="sl-composer-panel__field">
            <span>End time</span>
            <input
              type="time"
              required
              value={form.end_time}
              onChange={(e) => setForm({ ...form, end_time: e.target.value })}
            />
          </label>
        </div>

        <div className="sl-composer-panel__chips">
          <span className="sl-composer-panel__chips-label">Duration</span>
          {DURATION_PRESETS.map((p) => {
            const chipsDisabled = !form.start_time
            const active = selectedPresetMinutes === p.minutes
            return (
              <button
                key={p.minutes}
                type="button"
                disabled={chipsDisabled}
                title={chipsDisabled ? 'Set a start time first' : undefined}
                className={`sl-composer-panel__chip${active ? ' is-active' : ''}`}
                onClick={() => applyDurationPreset(p.minutes)}
              >
                {p.label}
              </button>
            )
          })}
        </div>

        {durationLabel ? (
          <p className="sl-composer-panel__summary">
            Session length: {durationLabel}
            {form.start_time && form.end_time ? (
              <span className="sl-composer-panel__summary-muted">
                {' '}
                ({form.start_time} – {form.end_time})
              </span>
            ) : null}
          </p>
        ) : null}

        {isPastDay ? (
          <p className="sl-composer-panel__notice">
            Sessions from a past day need admin review. You will be asked for a late reason when you submit the log.
          </p>
        ) : null}

        {localError ? <p className="sl-composer-panel__error">{localError}</p> : null}

        <div className="sl-composer-panel__actions">
          <button type="submit" className="sl-composer-panel__submit" disabled={submitting}>
            {submitting ? 'Adding…' : 'Add session & write log'}
          </button>
          {onCancel ? (
            <button type="button" className="sl-composer-panel__secondary" onClick={onCancel}>
              Cancel
            </button>
          ) : null}
        </div>
      </div>
    </form>
  )
}
