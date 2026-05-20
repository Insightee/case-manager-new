import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { isToday, todayIso } from '../../lib/therapistSchedule.js'
import { ForgotSessionForm } from '../daily-logs/ForgotSessionForm.jsx'

const MODES = [
  { value: 'HOME', label: 'Home' },
  { value: 'SCHOOL', label: 'School' },
  { value: 'CENTER', label: 'Center' },
  { value: 'ONLINE', label: 'Online' },
]

function pad2(n) {
  return String(n).padStart(2, '0')
}

function nowTimeInput() {
  const d = new Date()
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

function addMinutesToTime(timeStr, mins) {
  const [hh, mm] = timeStr.split(':').map(Number)
  const d = new Date()
  d.setHours(hh, mm + mins, 0, 0)
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

/**
 * Top-of-page session actions: start scheduled/booked visits, walk-in today, or log a past session.
 */
export function TherapistSessionComposer({
  lockCaseId = null,
  lockCaseLabel = '',
  upcomingSessions = [],
  bookedSlots = [],
  disabled = false,
  onSessionStarted,
  onManualSession,
  onError,
}) {
  const [mode, setMode] = useState('live')
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState(lockCaseId ? String(lockCaseId) : '')
  const [walkInStart, setWalkInStart] = useState(nowTimeInput)
  const [walkInEnd, setWalkInEnd] = useState(() => addMinutesToTime(nowTimeInput(), 60))
  const [walkInMode, setWalkInMode] = useState('HOME')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')

  useEffect(() => {
    if (lockCaseId) setCaseId(String(lockCaseId))
  }, [lockCaseId])

  useEffect(() => {
    apiFetch('/api/v1/cases?assigned=true&page_size=100')
      .then((data) => setCases(unwrapList(data)))
      .catch(() => setCases([]))
  }, [])

  const caseOptions = useMemo(() => {
    const map = new Map()
    for (const c of cases) {
      map.set(c.id, { case_id: c.id, child_name: c.child_name, case_code: c.case_code })
    }
    for (const s of upcomingSessions) {
      if (s.case_id && !map.has(s.case_id)) {
        map.set(s.case_id, { case_id: s.case_id, child_name: s.child_name, case_code: s.case_code })
      }
    }
    return [...map.values()]
  }, [cases, upcomingSessions])

  const selectedCaseId = caseId ? Number(caseId) : null

  const scheduledForCase = useMemo(() => {
    if (!selectedCaseId) return []
    const today = todayIso()
    return upcomingSessions.filter(
      (s) => s.case_id === selectedCaseId && s.status === 'SCHEDULED' && s.scheduled_date >= today,
    )
  }, [upcomingSessions, selectedCaseId])

  const bookingsForCase = useMemo(() => {
    if (!selectedCaseId) return []
    const today = todayIso()
    return bookedSlots.filter(
      (sl) => sl.case_id === selectedCaseId && sl.status === 'BOOKED' && sl.slot_date >= today,
    )
  }, [bookedSlots, selectedCaseId])

  async function startSession(sessionId) {
    setBusy(true)
    setLocalError('')
    try {
      await apiFetch(`/api/v1/sessions/${sessionId}/start`, { method: 'POST' })
      onSessionStarted?.()
    } catch (err) {
      const msg = err.message || 'Could not start session'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  async function handleWalkIn(e) {
    e.preventDefault()
    if (!selectedCaseId) {
      setLocalError('Choose a client first.')
      return
    }
    setBusy(true)
    setLocalError('')
    const today = todayIso()
    try {
      const created = await apiFetch('/api/v1/sessions', {
        method: 'POST',
        body: JSON.stringify({
          case_id: selectedCaseId,
          therapist_user_id: 0,
          scheduled_date: today,
          start_time: walkInStart,
          end_time: walkInEnd,
          mode: walkInMode,
          status: 'SCHEDULED',
        }),
      })
      await apiFetch(`/api/v1/sessions/${created.id}/start`, { method: 'POST' })
      onSessionStarted?.()
    } catch (err) {
      const msg = err.message || 'Could not start walk-in session'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  if (disabled) {
    return (
      <div className="ic-session-composer ic-session-composer--muted">
        <p>End your current session before starting another.</p>
      </div>
    )
  }

  return (
    <section className="ic-session-composer" aria-label="Add or start session">
      <div className="ic-session-composer__head">
        <div>
          <h2 className="ic-session-composer__title">Session</h2>
          <p className="ic-session-composer__sub">
            Start a visit now or log a session you forgot to record (needs client approval when backdated).
          </p>
        </div>
        <div className="ic-segment" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'live'}
            className={mode === 'live' ? 'active' : ''}
            onClick={() => setMode('live')}
          >
            Start now
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'past'}
            className={mode === 'past' ? 'active' : ''}
            onClick={() => setMode('past')}
          >
            Forgot to log
          </button>
        </div>
      </div>

      {localError ? <p className="ic-session-composer__error">{localError}</p> : null}

      {mode === 'past' ? (
        <ForgotSessionForm
          fallbackCases={caseOptions}
          initialCaseId={lockCaseId ? String(lockCaseId) : caseId}
          submitting={busy}
          onSubmit={async (payload) => {
            setBusy(true)
            try {
              await onManualSession?.(payload)
            } finally {
              setBusy(false)
            }
          }}
          onCancel={() => setMode('live')}
        />
      ) : (
        <div className="ic-session-composer__body">
          {lockCaseId && lockCaseLabel ? (
            <p className="ic-session-composer__locked-client">
              <span className="ic-session-composer__locked-label">Client</span>
              {lockCaseLabel}
            </p>
          ) : (
            <label className="ic-session-composer__field">
              <span>Client</span>
              <select
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
                className="ic-session-composer__input"
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
          )}

          {selectedCaseId ? (
            <>
              {scheduledForCase.length > 0 ? (
                <div className="ic-session-composer__group">
                  <p className="ic-session-composer__group-label">Scheduled sessions</p>
                  <ul className="ic-session-composer__options">
                    {scheduledForCase.map((s) => (
                      <li key={s.id}>
                        <div className="ic-session-option">
                          <div>
                            <strong>{s.scheduled_date}</strong>
                            <span>
                              {String(s.start_time).slice(0, 5)}–{String(s.end_time).slice(0, 5)} · {s.mode}
                            </span>
                          </div>
                          <button
                            type="button"
                            className="ic-btn ic-btn--primary"
                            disabled={busy}
                            onClick={() => startSession(s.id)}
                          >
                            Start
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {bookingsForCase.length > 0 ? (
                <div className="ic-session-composer__group">
                  <p className="ic-session-composer__group-label">Calendar bookings</p>
                  <ul className="ic-session-composer__options">
                    {bookingsForCase.map((sl) => (
                      <li key={sl.id}>
                        <div className="ic-session-option ic-session-option--booking">
                          <div>
                            <strong>{sl.slot_date}</strong>
                            <span>
                              {String(sl.start_time).slice(0, 5)}–{String(sl.end_time).slice(0, 5)}
                              {sl.booking_source === 'PARENT' ? ' · Parent booked' : ''}
                            </span>
                          </div>
                          <span className="ic-session-option__hint">
                            {isToday(sl.slot_date)
                              ? 'Use walk-in below if no scheduled session row'
                              : 'Opens on the day'}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <form className="ic-session-composer__walkin" onSubmit={handleWalkIn}>
                <p className="ic-session-composer__group-label">Walk-in today (no slot configured)</p>
                <div className="ic-session-composer__grid">
                  <label className="ic-session-composer__field">
                    <span>Start</span>
                    <input
                      type="time"
                      required
                      value={walkInStart}
                      onChange={(e) => setWalkInStart(e.target.value)}
                      className="ic-session-composer__input"
                    />
                  </label>
                  <label className="ic-session-composer__field">
                    <span>End</span>
                    <input
                      type="time"
                      required
                      value={walkInEnd}
                      onChange={(e) => setWalkInEnd(e.target.value)}
                      className="ic-session-composer__input"
                    />
                  </label>
                  <label className="ic-session-composer__field">
                    <span>Location</span>
                    <select
                      value={walkInMode}
                      onChange={(e) => setWalkInMode(e.target.value)}
                      className="ic-session-composer__input"
                    >
                      {MODES.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <button type="submit" className="ic-btn ic-btn--primary ic-session-composer__submit" disabled={busy}>
                  {busy ? 'Starting…' : 'Start session'}
                </button>
              </form>
            </>
          ) : (
            <p className="ic-session-composer__hint">Select a client to see scheduled visits or start a walk-in.</p>
          )}
        </div>
      )}
    </section>
  )
}
