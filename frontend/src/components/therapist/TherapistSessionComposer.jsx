import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTimeRange, todayIsoIST } from '../../lib/datetime.js'
import { unwrapList } from '../../lib/listApi.js'
import { pickNextStartableSessionToday } from '../../lib/sessionStartRules.js'
import { addDays, dateStr, startOfWeek } from '../scheduling/slotCalendarUtils.js'
import { ForgotSessionForm } from '../daily-logs/ForgotSessionForm.jsx'
import { ClinicalSubTabs } from '../clinical-ui/ClinicalSubTabBar.jsx'
import { SessionAbsenceSheet } from './SessionAbsenceSheet.jsx'
import { WeeklyScheduleDrawer } from './WeeklyScheduleDrawer.jsx'

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
 * Top-of-page session actions: start today's visit, log a past session, or log child absence.
 */
export function TherapistSessionComposer({
  lockCaseId = null,
  lockCaseLabel = '',
  upcomingSessions = [],
  disabled = false,
  caseProfileMode = false,
  onSessionStarted,
  onStartScheduledSession,
  onScheduleApplied,
  onManualSession,
  onError,
  onSelectedCaseChange,
}) {
  const { user } = useAuth()
  const [mode, setMode] = useState(caseProfileMode ? 'past' : 'live')
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState(lockCaseId ? String(lockCaseId) : '')
  const [walkInStart, setWalkInStart] = useState(nowTimeInput)
  const [walkInEnd, setWalkInEnd] = useState(() => addMinutesToTime(nowTimeInput(), 60))
  const [walkInMode, setWalkInMode] = useState('HOME')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')
  const [absenceSessionId, setAbsenceSessionId] = useState(null)
  const [scheduleOpen, setScheduleOpen] = useState(false)

  const scheduleWeekStart = useMemo(() => dateStr(startOfWeek(new Date())), [])
  const scheduleWeekEnd = useMemo(() => dateStr(addDays(startOfWeek(new Date()), 6)), [])

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
  const selectedCase = caseOptions.find((c) => c.case_id === selectedCaseId) || null

  const nextSessionToday = useMemo(
    () => pickNextStartableSessionToday(upcomingSessions),
    [upcomingSessions],
  )

  const hasScheduledToday = Boolean(nextSessionToday)

  useEffect(() => {
    onSelectedCaseChange?.(selectedCaseId)
  }, [selectedCaseId, onSelectedCaseChange])

  useEffect(() => {
    if (hasScheduledToday && nextSessionToday?.case_id && !lockCaseId) {
      setCaseId(String(nextSessionToday.case_id))
    }
  }, [hasScheduledToday, nextSessionToday?.case_id, lockCaseId])

  const todaySessionsForCase = useMemo(() => {
    if (!selectedCaseId) return []
    const today = todayIsoIST()
    return upcomingSessions.filter(
      (s) => s.case_id === selectedCaseId && s.scheduled_date === today && s.status === 'SCHEDULED',
    )
  }, [upcomingSessions, selectedCaseId])

  async function handleWalkIn(e) {
    e?.preventDefault?.()
    if (!selectedCaseId) {
      setLocalError('Choose a client first.')
      return
    }
    setBusy(true)
    setLocalError('')
    const today = todayIsoIST()
    try {
      const created = await apiFetch('/api/v1/sessions', {
        method: 'POST',
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
      const started = await apiFetch(`/api/v1/sessions/${created.id}/start`, { method: 'POST' })
      if (started?.invite_sent && started?.invite_email) {
        onSessionStarted?.({
          inviteSent: true,
          message: `Invite sent to ${started.invite_email} — they will join the Client portal.`,
        })
      } else {
        onSessionStarted?.()
      }
    } catch (err) {
      const msg = err.message || 'Could not start one-off session'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  async function handleStartScheduled() {
    if (!nextSessionToday) return
    setBusy(true)
    setLocalError('')
    try {
      await onStartScheduledSession?.(nextSessionToday.id, nextSessionToday)
    } catch (err) {
      const msg = err.message || 'Could not start scheduled session'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  function handleScheduleApplied(result) {
    const count = result?.booked_slot_count ?? 0
    setLocalError('')
    onScheduleApplied?.()
    onSessionStarted?.({
      message:
        count > 0
          ? `Added ${count} session${count === 1 ? '' : 's'} to your schedule.`
          : 'Schedule updated.',
    })
  }

  if (disabled) {
    return (
      <div className={`ic-session-composer ic-session-composer--muted${caseProfileMode ? ' ic-session-composer--case-profile' : ''}`}>
        <p>End your current session before logging another visit for this case.</p>
      </div>
    )
  }

  const caseProfileTabs = [
    { id: 'past', label: 'Log past session' },
    { id: 'absence', label: 'Child absence' },
  ]

  const scheduledTimeLabel = nextSessionToday
    ? formatDisplayDateTimeRange(
        nextSessionToday.scheduled_date,
        nextSessionToday.start_time,
        nextSessionToday.end_time,
      )
    : ''

  const scheduleCaseId = lockCaseId || selectedCaseId || nextSessionToday?.case_id || null

  return (
    <section
      className={`ic-session-composer sl-new-session${caseProfileMode ? ' ic-session-composer--case-profile' : ''}`}
      aria-label={caseProfileMode ? 'Log session for this case' : 'New session'}
    >
      <div className="sl-new-session__head">
        {!caseProfileMode ? (
          <h2 className="sl-new-session__title">
            <span className="material-symbols-outlined" aria-hidden="true">
              add_circle
            </span>
            New session
          </h2>
        ) : null}
        {caseProfileMode ? (
          <ClinicalSubTabs
            tabs={caseProfileTabs}
            activeTab={mode}
            onTabChange={setMode}
            ariaLabel="Session log type"
            className="clinical-logs-composer__tabs"
          />
        ) : (
          <div className="sl-new-session__tiles" role="tablist" aria-label="Session actions">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'live'}
              aria-label="Start now"
              className={`sl-new-session__tile${mode === 'live' ? ' is-active' : ''}`}
              onClick={() => {
                setMode('live')
                setLocalError('')
              }}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                play_circle
              </span>
              <span>Start now</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'past'}
              className={`sl-new-session__tile${mode === 'past' ? ' is-active' : ''}`}
              onClick={() => {
                setMode('past')
                setLocalError('')
              }}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                history
              </span>
              <span>Forgot to log</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'absence'}
              className={`sl-new-session__tile${mode === 'absence' ? ' is-active' : ''}`}
              onClick={() => {
                setMode('absence')
                setLocalError('')
              }}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                event_busy
              </span>
              <span>Child absence</span>
            </button>
          </div>
        )}
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
          onCancel={caseProfileMode ? undefined : () => setMode('live')}
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
              onSessionStarted?.({ message: msg })
            }}
            onError={(msg) => {
              setLocalError(msg)
              onError?.(msg)
            }}
          />
        </div>
      ) : !caseProfileMode && mode === 'live' ? (
        <div className="sl-live-panel">
          {hasScheduledToday ? (
            <article className="sl-live-panel__card sl-live-panel__card--scheduled">
              <div className="sl-live-panel__head">
                <span className="material-symbols-outlined" aria-hidden="true">
                  event_available
                </span>
                <div>
                  <span className="sl-live-panel__label">Today&apos;s scheduled session</span>
                  <strong className="sl-live-panel__title">
                    {nextSessionToday.child_name || nextSessionToday.case_code}
                  </strong>
                  <span className="sl-live-panel__meta">{scheduledTimeLabel}</span>
                </div>
              </div>
              {nextSessionToday.case_id ? (
                <Link to={`/therapist/cases/${nextSessionToday.case_id}`} className="sl-live-panel__case-link">
                  View case file
                </Link>
              ) : null}
              <button
                type="button"
                className="sl-live-panel__cta"
                disabled={busy}
                onClick={handleStartScheduled}
              >
                {busy ? 'Starting…' : 'Start scheduled session'}
              </button>
              <p className="sl-live-panel__hint">
                This is your visit for today — start here to clock in and write the log after.
              </p>
            </article>
          ) : (
            <article className="sl-live-panel__card sl-live-panel__card--oneoff">
              <div className="sl-live-panel__head">
                <span className="material-symbols-outlined" aria-hidden="true">
                  play_circle
                </span>
                <div>
                  <span className="sl-live-panel__label">One-off visit today</span>
                  <strong className="sl-live-panel__title">No appointment on today&apos;s calendar.</strong>
                </div>
              </div>

              {lockCaseId && lockCaseLabel ? (
                <p className="ic-session-composer__locked-client">
                  <span className="ic-session-composer__locked-label">Client</span>
                  {lockCaseLabel}
                </p>
              ) : (
                <label className="sl-walkin__label">
                  <span>Client</span>
                  <select
                    value={caseId}
                    onChange={(e) => {
                      setCaseId(e.target.value)
                      setLocalError('')
                    }}
                    className="ic-session-composer__input sl-walkin__select"
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

              {selectedCase && !lockCaseId ? (
                <div className="sl-walkin__profile">
                  <div>
                    <span className="sl-walkin__profile-label">Client profile summary</span>
                    <p className="sl-walkin__profile-meta">
                      {selectedCase.case_code ? (
                        <span>
                          Case: <strong>{selectedCase.case_code}</strong>
                        </span>
                      ) : null}
                    </p>
                  </div>
                  <Link to={`/therapist/cases/${selectedCase.case_id}`} className="sl-walkin__profile-link">
                    View full file
                  </Link>
                </div>
              ) : null}

              <form className="ic-session-composer__walkin sl-walkin__form" onSubmit={handleWalkIn}>
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
                <button
                  type="submit"
                  className="sl-live-panel__cta"
                  disabled={busy || !selectedCaseId}
                >
                  {busy ? 'Starting…' : 'Start one-off session'}
                </button>
              </form>
            </article>
          )}

          <div className="sl-live-panel__schedule-row">
            <p className="sl-live-panel__schedule-copy">
              {hasScheduledToday
                ? 'Need more visits on the calendar? Book recurring days and times.'
                : 'Want this client on the calendar going forward? Add a recurring schedule.'}
            </p>
            <button
              type="button"
              className="sl-live-panel__schedule-btn"
              onClick={() => setScheduleOpen(true)}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                calendar_add_on
              </span>
              Add to schedule
            </button>
          </div>
        </div>
      ) : null}

      <WeeklyScheduleDrawer
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        onApplied={handleScheduleApplied}
        weekStart={scheduleWeekStart}
        weekEnd={scheduleWeekEnd}
        therapistUserIdProp={user?.id}
        fixedCaseId={scheduleCaseId || undefined}
        initialTab="recurring"
        singleTab="recurring"
      />
    </section>
  )
}
