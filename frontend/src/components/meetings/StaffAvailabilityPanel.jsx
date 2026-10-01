import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import '../meetings/meetings-mobile.css'

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function createEmptyAvailabilityDraft() {
  return {
    rules: [],
    exceptions: [],
    booking_policy: {
      min_notice_minutes: 120,
      max_days_ahead: 60,
      buffer_minutes: 0,
      allowed_durations: [30, 45, 60, 90],
    },
  }
}

function normalizeAvailabilityDraft(payload) {
  const draft = createEmptyAvailabilityDraft()
  if (!payload) return draft
  draft.rules = Array.isArray(payload.rules) ? payload.rules : []
  draft.exceptions = Array.isArray(payload.exceptions) ? payload.exceptions : []
  draft.booking_policy = {
    min_notice_minutes: payload.booking_policy?.min_notice_minutes ?? 120,
    max_days_ahead: payload.booking_policy?.max_days_ahead ?? 60,
    buffer_minutes: payload.booking_policy?.buffer_minutes ?? 0,
    allowed_durations: Array.isArray(payload.booking_policy?.allowed_durations)
      ? payload.booking_policy.allowed_durations
      : [30, 45, 60, 90],
  }
  return draft
}

export function StaffAvailabilityPanel({
  userId,
  variant = 'admin',
  showGoogleCalendar = true,
  schedulingLink = null,
}) {
  const isTherapist = variant === 'therapist'
  const [availabilityDraft, setAvailabilityDraft] = useState(createEmptyAvailabilityDraft())
  const [availabilityLoading, setAvailabilityLoading] = useState(false)
  const [availabilitySaving, setAvailabilitySaving] = useState(false)
  const [availabilitySaved, setAvailabilitySaved] = useState(false)
  const [availabilityError, setAvailabilityError] = useState('')
  const [googleConnection, setGoogleConnection] = useState(null)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [googleError, setGoogleError] = useState('')
  const [newException, setNewException] = useState({
    date: '',
    type: 'CLOSED',
    start_time: '',
    end_time: '',
    reason: '',
  })

  useEffect(() => {
    if (!userId) return
    let cancelled = false
    setAvailabilityLoading(true)
    const requests = [apiFetch(`/api/v1/users/${userId}/availability`)]
    if (showGoogleCalendar) {
      requests.push(apiFetch('/api/v1/calendar/connections/google'))
    }
    Promise.all(requests)
      .then(([availability, connection]) => {
        if (cancelled) return
        setAvailabilityDraft(normalizeAvailabilityDraft(availability))
        if (showGoogleCalendar) setGoogleConnection(connection || null)
      })
      .catch((err) => {
        if (cancelled) return
        setAvailabilityError(err.message || 'Could not load availability settings')
      })
      .finally(() => {
        if (!cancelled) setAvailabilityLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [userId, showGoogleCalendar])

  const updateRule = useCallback((weekday, field, value) => {
    setAvailabilityDraft((draft) => {
      const rules = [...draft.rules]
      const index = rules.findIndex((row) => Number(row.weekday) === Number(weekday))
      const nextRow = index >= 0
        ? { ...rules[index], [field]: value }
        : {
          weekday,
          start_time: '10:00',
          end_time: '19:00',
          slot_granularity_minutes: 30,
          [field]: value,
        }
      if (index >= 0) {
        rules[index] = nextRow
      } else {
        rules.push(nextRow)
      }
      return { ...draft, rules }
    })
  }, [])

  const removeRule = useCallback((weekday) => {
    setAvailabilityDraft((draft) => ({
      ...draft,
      rules: draft.rules.filter((row) => Number(row.weekday) !== Number(weekday)),
    }))
  }, [])

  function addException() {
    if (!newException.date) {
      setAvailabilityError('Pick a date for the exception.')
      return
    }
    setAvailabilityDraft((draft) => ({
      ...draft,
      exceptions: [
        ...draft.exceptions,
        {
          date: newException.date,
          type: newException.type,
          start_time: newException.type === 'CUSTOM' ? (newException.start_time || null) : null,
          end_time: newException.type === 'CUSTOM' ? (newException.end_time || null) : null,
          reason: newException.reason.trim() || null,
        },
      ],
    }))
    setNewException({
      date: '',
      type: 'CLOSED',
      start_time: '',
      end_time: '',
      reason: '',
    })
  }

  async function saveAvailability() {
    if (!userId) return
    setAvailabilitySaving(true)
    setAvailabilityError('')
    setAvailabilitySaved(false)
    try {
      const result = await apiFetch(`/api/v1/users/${userId}/availability`, {
        method: 'PUT',
        body: JSON.stringify(availabilityDraft),
      })
      setAvailabilityDraft(normalizeAvailabilityDraft(result))
      setAvailabilitySaved(true)
      window.setTimeout(() => setAvailabilitySaved(false), 4000)
    } catch (err) {
      setAvailabilityError(err.message || 'Could not save availability settings')
    } finally {
      setAvailabilitySaving(false)
    }
  }

  async function connectGoogleCalendar() {
    setGoogleError('')
    try {
      setGoogleLoading(true)
      const result = await apiFetch('/api/v1/calendar/connections/google/authorize', { method: 'POST' })
      if (result?.authorization_url) {
        window.open(result.authorization_url, '_blank', 'noopener,noreferrer')
      } else {
        throw new Error('No Google authorization URL returned')
      }
    } catch (err) {
      setGoogleError(err.message || 'Could not start Google connection')
    } finally {
      setGoogleLoading(false)
    }
  }

  async function disconnectGoogleCalendar() {
    setGoogleError('')
    try {
      setGoogleLoading(true)
      await apiFetch('/api/v1/calendar/connections/google', { method: 'DELETE' })
      setGoogleConnection({ is_connected: false })
    } catch (err) {
      setGoogleError(err.message || 'Could not disconnect Google Calendar')
    } finally {
      setGoogleLoading(false)
    }
  }

  return (
    <section className="card" style={{ marginBottom: 20, padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
        <div>
          <p className="admin-muted" style={{ margin: 0, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>My availability</p>
          <h3 style={{ margin: '4px 0 0' }}>
            {isTherapist ? 'One schedule for meetings and sessions' : 'Weekday rules, exceptions, and Google sync'}
          </h3>
        </div>
        <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={saveAvailability} disabled={availabilitySaving || availabilityLoading}>
          {availabilitySaving ? 'Saving…' : 'Save availability'}
        </button>
      </div>
      <p style={{ margin: '0 0 12px', fontSize: '0.85rem', color: '#64748b' }}>
        {isTherapist
          ? 'These hours apply to CM meetings, parent booking, and session scheduling. Changes sync to your weekly schedule automatically.'
          : 'Insighte owns meetings; Google edits are ignored. Use this panel to keep your shared booking window current.'}
      </p>
      {schedulingLink ? (
        <p style={{ margin: '0 0 12px', fontSize: '0.85rem' }}>
          <Link to={schedulingLink} style={{ color: '#4338ca', fontWeight: 600 }}>
            Open session calendar →
          </Link>
        </p>
      ) : null}
      {availabilityError ? <p className="admin-alert admin-alert--error">{availabilityError}</p> : null}
      {availabilitySaved ? (
        <p className="admin-alert admin-alert--success">
          {isTherapist
            ? 'Availability saved — meetings, parent slots, and session materialization now use these hours.'
            : 'Availability saved — therapists will only see these slots when booking with you.'}
        </p>
      ) : null}
      {googleError ? <p className="admin-alert admin-alert--error">{googleError}</p> : null}

      <div style={{ display: 'grid', gap: 10, marginBottom: 14 }}>
        {WEEKDAY_LABELS.map((label, weekday) => {
          const rule = availabilityDraft.rules.find((row) => Number(row.weekday) === weekday)
          const active = Boolean(rule)
          const row = rule || { weekday, start_time: '10:00', end_time: '19:00', slot_granularity_minutes: 30 }
          return (
            <div key={label} style={{ border: '1px solid #e2e8f0', borderRadius: 12, padding: 10, background: '#fff' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 8 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: '#0f172a' }}>
                  <input type="checkbox" checked={active} onChange={(e) => (e.target.checked ? updateRule(weekday, 'weekday', weekday) : removeRule(weekday))} />
                  {label}
                </label>
                <span className="admin-muted" style={{ fontSize: '0.75rem' }}>{active ? 'Open' : 'Off'}</span>
              </div>
              {active ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8 }}>
                  <input
                    type="time"
                    className="admin-input"
                    value={row.start_time}
                    onChange={(e) => updateRule(weekday, 'start_time', e.target.value)}
                  />
                  <input
                    type="time"
                    className="admin-input"
                    value={row.end_time}
                    onChange={(e) => updateRule(weekday, 'end_time', e.target.value)}
                  />
                  <input
                    type="number"
                    min="1"
                    className="admin-input"
                    value={row.slot_granularity_minutes || 30}
                    onChange={(e) => updateRule(weekday, 'slot_granularity_minutes', Number(e.target.value) || 30)}
                  />
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                    <input
                      type="date"
                      className="admin-input"
                      value={row.effective_from || ''}
                      onChange={(e) => updateRule(weekday, 'effective_from', e.target.value || null)}
                    />
                    <input
                      type="date"
                      className="admin-input"
                      value={row.effective_to || ''}
                      onChange={(e) => updateRule(weekday, 'effective_to', e.target.value || null)}
                    />
                  </div>
                </div>
              ) : null}
            </div>
          )
        })}
      </div>

      <div className="meetings-availability-policy-grid">
        <label className="admin-label">
          Min notice (minutes)
          <input
            type="number"
            min="0"
            className="admin-input"
            value={availabilityDraft.booking_policy.min_notice_minutes}
            onChange={(e) => setAvailabilityDraft((draft) => ({
              ...draft,
              booking_policy: { ...draft.booking_policy, min_notice_minutes: Number(e.target.value) || 0 },
            }))}
          />
        </label>
        <label className="admin-label">
          Max days ahead
          <input
            type="number"
            min="0"
            className="admin-input"
            value={availabilityDraft.booking_policy.max_days_ahead}
            onChange={(e) => setAvailabilityDraft((draft) => ({
              ...draft,
              booking_policy: { ...draft.booking_policy, max_days_ahead: Number(e.target.value) || 0 },
            }))}
          />
        </label>
        <label className="admin-label">
          Buffer (minutes)
          <input
            type="number"
            min="0"
            className="admin-input"
            value={availabilityDraft.booking_policy.buffer_minutes}
            onChange={(e) => setAvailabilityDraft((draft) => ({
              ...draft,
              booking_policy: { ...draft.booking_policy, buffer_minutes: Number(e.target.value) || 0 },
            }))}
          />
        </label>
        <label className="admin-label">
          Allowed durations
          <input
            type="text"
            className="admin-input"
            value={availabilityDraft.booking_policy.allowed_durations.join(', ')}
            onChange={(e) => setAvailabilityDraft((draft) => ({
              ...draft,
              booking_policy: {
                ...draft.booking_policy,
                allowed_durations: e.target.value.split(',').map((value) => Number(value.trim())).filter(Boolean),
              },
            }))}
          />
        </label>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 8 }}>
          <strong>Exceptions</strong>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={addException}>Add exception</button>
        </div>
        <div className="meetings-availability-exceptions-grid">
          <input type="date" className="admin-input" value={newException.date} onChange={(e) => setNewException((draft) => ({ ...draft, date: e.target.value }))} />
          <select className="admin-input" value={newException.type} onChange={(e) => setNewException((draft) => ({ ...draft, type: e.target.value }))}>
            <option value="CLOSED">Closed</option>
            <option value="CUSTOM">Custom window</option>
          </select>
          <input type="time" className="admin-input" value={newException.start_time} onChange={(e) => setNewException((draft) => ({ ...draft, start_time: e.target.value }))} />
          <input type="time" className="admin-input" value={newException.end_time} onChange={(e) => setNewException((draft) => ({ ...draft, end_time: e.target.value }))} />
          <input type="text" className="admin-input" placeholder="Reason" value={newException.reason} onChange={(e) => setNewException((draft) => ({ ...draft, reason: e.target.value }))} />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {availabilityDraft.exceptions.length > 0 ? availabilityDraft.exceptions.map((item, index) => (
            <span key={`${item.date}-${index}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid #cbd5e1', borderRadius: 999, padding: '5px 10px', fontSize: '0.8rem', color: '#334155', background: '#f8fafc' }}>
              {item.date} · {item.type}{item.reason ? ` · ${item.reason}` : ''}
              <button
                type="button"
                onClick={() => setAvailabilityDraft((draft) => ({ ...draft, exceptions: draft.exceptions.filter((_, idx) => idx !== index) }))}
                style={{ border: 'none', background: 'transparent', color: '#dc2626', cursor: 'pointer', padding: 0 }}
              >
                ×
              </button>
            </span>
          )) : <span className="admin-muted">No exceptions yet.</span>}
        </div>
      </div>

      {showGoogleCalendar ? (
        <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 14, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <strong>Google Calendar</strong>
            <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#64748b' }}>
              {googleConnection?.is_connected ? `Connected to ${googleConnection.google_account_email || 'Google'}` : 'Not connected yet.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {googleConnection?.is_connected ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={disconnectGoogleCalendar} disabled={googleLoading}>
                Disconnect
              </button>
            ) : (
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={connectGoogleCalendar} disabled={googleLoading}>
                Connect Google
              </button>
            )}
          </div>
        </div>
      ) : null}
    </section>
  )
}
