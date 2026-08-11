import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { patchCachesAfterAbsenceSubmit } from '../../lib/therapistSessionLogCache.js'
import { apiFetch } from '../../lib/apiClient.js'
import { todayIsoIST } from '../../lib/datetime.js'
import { isAbsenceConflict, isPendingLogBlock } from '../../lib/sessionStartRules.js'
import { unwrapList } from '../../lib/listApi.js'
import { ExistingSessionForDateCard } from '../daily-logs/ExistingSessionForDateCard.jsx'
import { ForgotSessionForm } from '../daily-logs/ForgotSessionForm.jsx'
// TODO: re-enable when therapist self-onboarding is allowed again
// import { NewClientIntakeForm } from '../daily-logs/NewClientIntakeForm.jsx'
import { SessionAbsenceSheet } from './SessionAbsenceSheet.jsx'
import { MigrationBackfillBanner } from './MigrationBackfillBanner.jsx'

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
  selectedCaseId: selectedCaseIdProp = undefined,
  upcomingSessions = [],
  disabled = false,
  liveBlocked = false,
  pendingLogBlocked = false,
  existingSessionConflict = null,
  walkInConflict = null,
  onExistingSessionAction,
  onDismissExistingSessionConflict,
  onDismissWalkInConflict,
  onScheduledSessionExists,
  onWalkInSessionConflict,
  onSessionStarted,
  onManualSession,
  onError,
  onSelectedCaseChange,
}) {
  const { user } = useAuth()
  const [mode, setMode] = useState('live')
  const [cases, setCases] = useState([])
  const [internalCaseId, setInternalCaseId] = useState(lockCaseId ? String(lockCaseId) : '')
  const [walkInStart, setWalkInStart] = useState(nowTimeInput)
  const [walkInEnd, setWalkInEnd] = useState(() => addMinutesToTime(nowTimeInput(), 60))
  const [walkInMode, setWalkInMode] = useState('HOME')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')
  const [composerSuccess, setComposerSuccess] = useState('')
  const [absenceSessionId, setAbsenceSessionId] = useState(null)
  const [migrationInfo, setMigrationInfo] = useState(null)

  useEffect(() => {
    if (lockCaseId) setInternalCaseId(String(lockCaseId))
  }, [lockCaseId])

  const caseId = lockCaseId
    ? String(lockCaseId)
    : selectedCaseIdProp !== undefined
      ? selectedCaseIdProp
        ? String(selectedCaseIdProp)
        : ''
      : internalCaseId

  function setCaseSelection(nextValue) {
    if (lockCaseId) return
    if (selectedCaseIdProp === undefined) {
      setInternalCaseId(nextValue)
    }
    onSelectedCaseChange?.(nextValue ? Number(nextValue) : null)
  }

  useEffect(() => {
    apiFetch('/api/v1/leave/migration-info')
      .then((data) => setMigrationInfo(data))
      .catch(() => setMigrationInfo(null))
  }, [])

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
    if (selectedCaseIdProp !== undefined || lockCaseId) return
    onSelectedCaseChange?.(selectedCaseId)
  }, [selectedCaseId, selectedCaseIdProp, lockCaseId, onSelectedCaseChange])

  const blockComposerForLiveSession = liveBlocked || disabled
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
    onDismissWalkInConflict?.()
    const today = todayIsoIST()
    const idempotencyKey = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`

    try {
      let created
      try {
        created = await apiFetch('/api/v1/sessions', {
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
      } catch (err) {
        if (err?.status === 409 && isPendingLogBlock(err.detail)) {
          setLocalError(
            err.detail.message ||
              'This client\'s previous visit still needs a log before starting another session.',
          )
          return
        }
        if (err?.status === 409 && isAbsenceConflict(err.detail)) {
          setLocalError(err.detail.message || 'Session cannot be started because of child absence.')
          return
        }
        if (err?.status === 409 && err?.detail?.code === 'EXISTING_SESSION_FOR_DATE') {
          const detail = err.detail
          const status = detail.session_status || detail.status
          if (status === 'SCHEDULED') {
            onScheduledSessionExists?.({
              sessionId: detail.existing_session_id || detail.session_id,
              caseId: detail.case_id,
              message:
                detail.message ||
                'A scheduled session already exists for this client today.',
            })
          } else {
            onWalkInSessionConflict?.(detail)
          }
          return
        }
        throw err
      }
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
    } finally {
      setBusy(false)
    }
  }

  function renderClientPicker({ onChangeExtra } = {}) {
    if (lockCaseId && lockCaseLabel) {
      return (
        <p className="ic-session-composer__locked-client">
          <span className="ic-session-composer__locked-label">Client</span>
          {lockCaseLabel}
        </p>
      )
    }

    return (
      <div className="ic-session-composer__client-pick">
        <label className="ic-session-composer__field">
          <span>Client</span>
          <select
            value={caseId}
            onChange={(e) => {
              setCaseSelection(e.target.value)
              onChangeExtra?.(e.target.value)
            }}
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
        {caseId ? (
          <button
            type="button"
            className="ic-session-composer__clear-client"
            onClick={() => {
              setCaseSelection('')
              onChangeExtra?.('')
            }}
          >
            View all clients
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <section className="ic-session-composer" aria-label="Add or start session">
      <MigrationBackfillBanner migrationInfo={migrationInfo} style={{ marginBottom: 12 }} />
      <div className="ic-session-composer__head">
        <h2 className="ic-session-composer__title">Session</h2>
        <div className="ic-segment ic-segment--primary" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'live'}
            className={mode === 'live' ? 'active' : ''}
            onClick={() => setMode('live')}
            disabled={blockComposerForLiveSession}
          >
            Start now
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'past'}
            className={mode === 'past' ? 'active' : ''}
            onClick={() => setMode('past')}
            disabled={blockComposerForLiveSession}
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

      {blockComposerForLiveSession && liveBlocked ? (
        <p className="ic-session-composer__live-blocked" role="status">
          A session is in progress — end it above to start another visit.
        </p>
      ) : null}

      {mode === 'past' && !blockComposerForLiveSession ? (
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
          {renderClientPicker({
            onChangeExtra: () => setAbsenceSessionId(null),
          })}
          <SessionAbsenceSheet
            sessions={todaySessionsForCase}
            selectedSessionId={absenceSessionId || todaySessionsForCase[0]?.id}
            onSessionChange={setAbsenceSessionId}
            disabled={busy}
            caseId={selectedCaseId}
            migrationInfo={migrationInfo}
            onSuccess={(msg, submittedSessionId) => {
              setLocalError('')
              setComposerSuccess(msg || 'Child absent logged — parent or admin will review.')
              const sid = submittedSessionId || absenceSessionId || todaySessionsForCase[0]?.id
              if (sid && user?.id) {
                patchCachesAfterAbsenceSubmit(sid, user.id)
              }
              onSessionStarted?.({ message: msg, sessionId: sid })
            }}
            onError={(msg) => {
              setLocalError(msg)
              setComposerSuccess('')
            }}
          />
          {composerSuccess ? (
            <p className="ic-composer-inline-success" role="status">
              {composerSuccess}
            </p>
          ) : null}
        </div>
      ) : mode === 'live' && !blockComposerForLiveSession ? (
        <div className="ic-session-composer__body">
          {renderClientPicker()}

          {pendingLogBlocked ? (
            <p className="ic-session-composer__live-blocked" role="status">
              This client&apos;s previous visit still needs a log before you can start another session for them.
              Choose another client above, complete the log in the banner, or use Forgot to log.
            </p>
          ) : null}

          {!pendingLogBlocked && walkInConflict ? (
            <ExistingSessionForDateCard
              conflict={walkInConflict}
              onAction={onExistingSessionAction}
              onDismiss={onDismissWalkInConflict}
            />
          ) : !pendingLogBlocked && selectedCaseId ? (
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
          ) : !selectedCaseId ? (
            <p className="ic-session-composer__hint">
              Select a client for walk-in, or start a scheduled visit in Upcoming sessions below.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}
