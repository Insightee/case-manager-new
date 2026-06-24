import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { todayIsoIST } from '../../lib/datetime.js'
import { unwrapList } from '../../lib/listApi.js'
import { ForgotSessionForm } from '../daily-logs/ForgotSessionForm.jsx'
// TODO: re-enable when therapist self-onboarding is allowed again
// import { NewClientIntakeForm } from '../daily-logs/NewClientIntakeForm.jsx'
import { SessionAbsenceSheet } from './SessionAbsenceSheet.jsx'

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
 * Top-of-page session actions: walk-in today, log a past session, or log child absence.
 */
export function TherapistSessionComposer({
  lockCaseId = null,
  lockCaseLabel = '',
  upcomingSessions = [],
  disabled = false,
  liveBlocked = false,
  existingSessionConflict = null,
  onExistingSessionAction,
  onDismissExistingSessionConflict,
  onSessionStarted,
  onManualSession,
  onError,
  onSelectedCaseChange,
}) {
  const { user } = useAuth()
  const [mode, setMode] = useState('live')
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState(lockCaseId ? String(lockCaseId) : '')
  const [walkInStart, setWalkInStart] = useState(nowTimeInput)
  const [walkInEnd, setWalkInEnd] = useState(() => addMinutesToTime(nowTimeInput(), 60))
  const [walkInMode, setWalkInMode] = useState('HOME')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')
  const [composerSuccess, setComposerSuccess] = useState('')
  const [absenceSessionId, setAbsenceSessionId] = useState(null)

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
      map.set(c.id, {
        case_id: c.id,
        child_name: c.child_name,
        case_code: c.case_code,
        product_module: c.product_module,
      })
    }
    for (const s of upcomingSessions) {
      if (s.case_id && !map.has(s.case_id)) {
        map.set(s.case_id, { case_id: s.case_id, child_name: s.child_name, case_code: s.case_code })
      }
    }
    return [...map.values()]
  }, [cases, upcomingSessions])

  const selectedCaseId = caseId ? Number(caseId) : null

  useEffect(() => {
    onSelectedCaseChange?.(selectedCaseId)
  }, [selectedCaseId, onSelectedCaseChange])

  const blockLive = liveBlocked || disabled
  const absenceAllowedStatuses = new Set(['SCHEDULED', 'IN_PROGRESS'])
  const todaySessionsForCase = useMemo(() => {
    if (!selectedCaseId) return []
    const today = todayIsoIST()
    return upcomingSessions.filter(
      (s) =>
        s.case_id === selectedCaseId &&
        s.scheduled_date === today &&
        absenceAllowedStatuses.has(s.status),
    )
  }, [upcomingSessions, selectedCaseId])

  async function handleWalkIn(e) {
    e.preventDefault()
    if (!selectedCaseId) {
      setLocalError('Choose a client first.')
      return
    }
    if (busy) return
    setBusy(true)
    setLocalError('')
    const today = todayIsoIST()
    const idempotencyKey = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`

    try {
      const created = await apiFetch('/api/v1/sessions', {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify({
          case_id: selectedCaseId,
          therapist_user_id: user?.id ?? 0,
          scheduled_date: today,
          start_time: walkInStart,
          end_time: walkInEnd,
          mode: walkInMode,
          status: 'SCHEDULED',
        }),
      })
      const started = await apiFetch(`/api/v1/sessions/${created.id}/start`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
      })
      if (started?.invite_sent && started?.invite_email) {
        onSessionStarted?.({
          inviteSent: true,
          message: `Invite sent to ${started.invite_email} — they will join the Client portal.`,
        })
      } else {
        onSessionStarted?.()
      }
    } catch (err) {
      const msg = err.message || 'Could not start walk-in session'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="ic-session-composer" aria-label="Add or start session">
      <div className="ic-session-composer__head">
        <h2 className="ic-session-composer__title">Session</h2>
        <div className="ic-segment ic-segment--primary" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'live'}
            className={mode === 'live' ? 'active' : ''}
            onClick={() => setMode('live')}
            disabled={blockLive}
          >
            Start now
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'past'}
            className={mode === 'past' ? 'active' : ''}
            onClick={() => setMode('past')}
            disabled={blockLive}
          >
            Forgot to log
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'absence'}
            className={mode === 'absence' ? 'active' : ''}
            onClick={() => setMode('absence')}
          >
            Child absence
          </button>
        </div>
      </div>

      {localError ? <p className="ic-session-composer__error">{localError}</p> : null}

      {/* TODO: re-enable when therapist self-onboarding is allowed again
      {mode === 'newClient' ? (
        <NewClientIntakeForm
          disabled={busy}
          onCancel={() => setMode('live')}
          onCreated={(result) => {
            setCases((prev) => [
              ...prev,
              {
                id: result.case_id,
                child_name: result.child_name,
                case_code: result.case_code,
              },
            ])
            setCaseId(String(result.case_id))
            setMode('live')
            setLocalError('')
            onSessionStarted?.({
              message: `Client ${result.case_code} created. Start a session to send the parent invite.`,
            })
          }}
        />
      ) : null}
      */}

      {blockLive ? (
        <p className="ic-session-composer__live-blocked" role="status">
          A session is in progress — end it above to start another visit.
        </p>
      ) : null}

      {mode === 'past' && !blockLive ? (
        <ForgotSessionForm
          fallbackCases={caseOptions}
          initialCaseId={lockCaseId ? String(lockCaseId) : caseId}
          submitting={busy}
          existingSessionConflict={existingSessionConflict}
          onExistingSessionAction={onExistingSessionAction}
          onDismissExistingSessionConflict={onDismissExistingSessionConflict}
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
      ) : mode === 'absence' ? (
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
                onChange={(e) => {
                  setCaseId(e.target.value)
                  setAbsenceSessionId(null)
                }}
                className="ic-session-composer__input"
              >
                <option value="">Choose client…</option>
                {caseOptions.map((c) => (
                  <option key={c.case_id} value={c.case_id}>
                    {c.child_name || c.case_code}
                  </option>
                ))}
              </select>
            </label>
          )}
          <SessionAbsenceSheet
            sessions={todaySessionsForCase}
            selectedSessionId={absenceSessionId || todaySessionsForCase[0]?.id}
            onSessionChange={setAbsenceSessionId}
            disabled={busy}
            onSuccess={(msg) => {
              setLocalError('')
              setComposerSuccess(msg || 'Child absent logged — parent or admin will review.')
              onSessionStarted?.({ message: msg })
            }}
            onError={(msg) => {
              setLocalError(msg)
              setComposerSuccess('')
              onError?.(msg)
            }}
          />
          {composerSuccess ? (
            <p className="ic-composer-inline-success" role="status">
              {composerSuccess}
            </p>
          ) : null}
        </div>
      ) : mode === 'live' && !blockLive ? (
        <div className="ic-session-composer__body">
          {lockCaseId && lockCaseLabel ? (
            <p className="ic-session-composer__locked-client">
              <span className="ic-session-composer__locked-label">Client</span>
              {lockCaseLabel}
            </p>
          ) : (
            <div className="ic-session-composer__client-pick">
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
              {/* TODO: re-enable when therapist self-onboarding is allowed again
              <button
                type="button"
                className="ic-session-composer__add-client"
                onClick={() => setMode('newClient')}
              >
                + Add new client
              </button>
              */}
            </div>
          )}

          {selectedCaseId ? (
            <>
              <form className="ic-session-composer__walkin" onSubmit={handleWalkIn}>
                <p className="ic-session-composer__walkin-title">
                  <strong>Walk-in today</strong>
                  <span className="ic-session-composer__walkin-note"> (Use if slots not configured)</span>
                </p>
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
            <p className="ic-session-composer__hint">
              Select a client for walk-in, or start a scheduled visit in Upcoming sessions below.
            </p>
          )}
        </div>
      ) : null}
    </section>
  )
}
