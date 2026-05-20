import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'

const MODES = [
  { value: 'HOME', label: 'Home' },
  { value: 'SCHOOL', label: 'School' },
  { value: 'CENTER', label: 'Center' },
  { value: 'ONLINE', label: 'Online' },
]

const DURATION_PRESETS = [
  { label: '30 min', minutes: 30 },
  { label: '45 min', minutes: 45 },
  { label: '1 hour', minutes: 60 },
  { label: '1.5 hours', minutes: 90 },
]

function pad2(n) {
  return String(n).padStart(2, '0')
}

export function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
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
    session_date: todayIso(),
    start_time: toTimeInput(start),
    end_time: toTimeInput(end),
    mode: 'HOME',
  }
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
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

const fieldStyle = {
  display: 'block',
  width: '100%',
  marginTop: 6,
  padding: '10px 12px',
  borderRadius: 10,
  border: '1px solid #d1d5db',
  fontSize: '0.9375rem',
  minHeight: 44,
  boxSizing: 'border-box',
}

const labelStyle = {
  fontSize: '0.8125rem',
  fontWeight: 600,
  color: '#374151',
}

export function ForgotSessionForm({ fallbackCases = [], onSubmit, onCancel, submitting, initialCaseId = '' }) {
  const [form, setForm] = useState(() => ({
    ...defaultForgotSession(),
    case_id: initialCaseId ? String(initialCaseId) : '',
  }))
  const [cases, setCases] = useState([])
  const [localError, setLocalError] = useState('')

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

  const startDt = combineDateAndTime(form.session_date, form.start_time)
  const endDt = combineDateAndTime(form.session_date, form.end_time)
  const durationLabel = formatDurationLabel(startDt, endDt)
  const isPastDay = form.session_date < todayIso()
  const isToday = form.session_date === todayIso()

  function setStartTime(time) {
    setForm((f) => ({ ...f, start_time: time }))
  }

  function applyDurationPreset(minutes) {
    if (!form.start_time) return
    const start = combineDateAndTime(form.session_date, form.start_time)
    if (!start) return
    const end = new Date(start.getTime() + minutes * 60000)
    setForm((f) => ({ ...f, end_time: toTimeInput(end) }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    setLocalError('')
    if (!form.case_id) {
      setLocalError('Select a client.')
      return
    }
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
    const today = todayIso()
    if (form.session_date > today) {
      setLocalError('Session date cannot be in the future.')
      return
    }
    if (isToday && end > new Date()) {
      setLocalError('End time cannot be in the future for today.')
      return
    }
    onSubmit({
      case_id: Number(form.case_id),
      scheduled_date: form.session_date,
      actual_start_at: start.toISOString(),
      actual_end_at: end.toISOString(),
      mode: form.mode,
      isPastDay,
    })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="forgot-session-form"
      style={{
        background: 'linear-gradient(180deg, #f8fafc 0%, #fff 100%)',
        border: '1px solid #e2e8f0',
        borderRadius: 16,
        padding: '18px 20px',
        marginBottom: 16,
        boxShadow: '0 4px 20px rgba(15, 23, 42, 0.06)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>Log a session you missed</h4>
          <p style={{ margin: '6px 0 0', fontSize: '0.8125rem', color: '#64748b', lineHeight: 1.45 }}>
            Pick the visit date, then enter when the session started and ended. No live timer needed.
          </p>
        </div>
        <button
          type="button"
          onClick={onCancel}
          aria-label="Close"
          style={{
            border: 'none',
            background: '#f1f5f9',
            borderRadius: 8,
            width: 32,
            height: 32,
            cursor: 'pointer',
            color: '#64748b',
            fontSize: '1.1rem',
            flexShrink: 0,
          }}
        >
          ×
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {caseOptions.length > 1 || !initialCaseId ? (
          <label style={labelStyle}>
            Client
            <select
              required
              value={form.case_id}
              onChange={(e) => setForm({ ...form, case_id: e.target.value })}
              style={fieldStyle}
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
          <p style={{ margin: 0, fontSize: '0.875rem', fontWeight: 600, color: '#374151' }}>
            {caseOptions[0]?.child_name || caseOptions[0]?.case_code || 'Selected client'}
          </p>
        )}

        <label style={labelStyle}>
          Session date
          <input
            type="date"
            required
            max={todayIso()}
            value={form.session_date}
            onChange={(e) => setForm({ ...form, session_date: e.target.value })}
            style={fieldStyle}
          />
          <span style={{ display: 'block', marginTop: 4, fontSize: '0.75rem', color: '#94a3b8' }}>
            {formatDisplayDate(form.session_date)}
            {isToday ? ' · Today' : isPastDay ? ' · Past date' : ''}
          </span>
        </label>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: 12,
          }}
        >
          <label style={labelStyle}>
            Start time
            <input
              type="time"
              required
              value={form.start_time}
              onChange={(e) => setStartTime(e.target.value)}
              style={fieldStyle}
            />
          </label>
          <label style={labelStyle}>
            End time
            <input
              type="time"
              required
              value={form.end_time}
              onChange={(e) => setForm({ ...form, end_time: e.target.value })}
              style={fieldStyle}
            />
          </label>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>Duration:</span>
          {DURATION_PRESETS.map((p) => (
            <button
              key={p.minutes}
              type="button"
              onClick={() => applyDurationPreset(p.minutes)}
              style={{
                padding: '4px 10px',
                borderRadius: 20,
                border: '1px solid #e2e8f0',
                background: '#fff',
                fontSize: '0.75rem',
                fontWeight: 600,
                color: '#475569',
                cursor: 'pointer',
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {durationLabel ? (
          <p
            style={{
              margin: 0,
              padding: '10px 12px',
              borderRadius: 10,
              background: '#eef2ff',
              color: '#3730a3',
              fontSize: '0.875rem',
              fontWeight: 600,
            }}
          >
            Session length: {durationLabel}
            {form.start_time && form.end_time ? (
              <span style={{ fontWeight: 400, color: '#6366f1' }}>
                {' '}
                ({form.start_time} – {form.end_time})
              </span>
            ) : null}
          </p>
        ) : null}

        {isPastDay ? (
          <p
            style={{
              margin: 0,
              padding: '10px 12px',
              borderRadius: 10,
              background: '#fffbeb',
              border: '1px solid #fde047',
              color: '#a16207',
              fontSize: '0.8125rem',
            }}
          >
            Sessions from a past day need admin review. You will be asked for a late reason when you submit the log.
          </p>
        ) : null}

        <label style={labelStyle}>
          Location
          <select
            value={form.mode}
            onChange={(e) => setForm({ ...form, mode: e.target.value })}
            style={fieldStyle}
          >
            {MODES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>

        {localError ? (
          <p style={{ margin: 0, fontSize: '0.8125rem', color: '#b91c1c' }}>{localError}</p>
        ) : null}

        <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
          <button
            type="submit"
            disabled={submitting}
            style={{
              flex: 1,
              padding: '12px 16px',
              borderRadius: 10,
              background: '#6366f1',
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.9375rem',
              border: 'none',
              cursor: submitting ? 'not-allowed' : 'pointer',
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? 'Adding…' : 'Add session & write log'}
          </button>
          <button
            type="button"
            onClick={onCancel}
            style={{
              padding: '12px 16px',
              borderRadius: 10,
              border: '1px solid #d1d5db',
              background: '#fff',
              fontWeight: 600,
              fontSize: '0.875rem',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    </form>
  )
}
