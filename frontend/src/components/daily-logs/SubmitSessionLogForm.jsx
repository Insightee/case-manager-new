import { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { clearLogDraft, getLogDraft, listPendingDrafts, markDraftSynced, saveLogDraft } from '../../lib/logDraftStore.js'
import {
  formatSessionTimeRange,
  canEditLog,
  isLogEditable,
  isLogResubmittable,
  logToFormState,
  todayIsoIST,
  validateSessionLogForm,
} from '../../lib/sessionLogUtils.js'
import { formatDisplayDate, formatTimeIST } from '../../lib/datetime.js'
import { getDurationComplianceWarning } from '../../lib/sessionDurationCompliance.js'
import { SessionBrief } from './SessionBrief.jsx'
import { SessionCancelConfirmDialog } from './SessionCancelConfirmDialog.jsx'
import { ENABLE_STRUCTURED_EVIDENCE } from '../../lib/productFeatureFlags.js'

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

const PARTICIPATION_OPTS = [
  { value: 'engaged', label: 'Engaged' },
  { value: 'mixed', label: 'Mixed' },
  { value: 'supported', label: 'Supported' },
]
const SUPPORT_OPTS = [
  { value: 'independent', label: 'Independent' },
  { value: 'occasional', label: 'Occasional' },
  { value: 'consistent', label: 'Consistent' },
]
const ACHIEVEMENT_OPTS = [
  { value: 'emerging', label: 'Emerging' },
  { value: 'progressing', label: 'Progressing' },
  { value: 'demonstrated', label: 'Demonstrated' },
]
const STRATEGY_OPTS = [
  { value: 'helpful', label: 'Helpful' },
  { value: 'partly_helpful', label: 'Partly helpful' },
  { value: 'rejected', label: 'Not this time' },
  { value: 'needs_adaptation', label: 'Needs adapting' },
]

function evidencePayload(goalTaps, strategyTaps) {
  if (!ENABLE_STRUCTURED_EVIDENCE) return {}
  const goal_entries = Object.entries(goalTaps)
    .filter(([, t]) => t.participation && t.support_level && t.achievement)
    .map(([goalId, t]) => ({
      goal_id: Number(goalId),
      participation: t.participation,
      support_level: t.support_level,
      achievement: t.achievement,
      note: t.note || undefined,
    }))
  const strategy_events = Object.entries(strategyTaps)
    .filter(([, t]) => t.response)
    .map(([strategyId, t]) => ({
      strategy_id: Number(strategyId),
      response: t.response,
      note: t.note || undefined,
    }))
  return { goal_entries, strategy_events }
}

function tapsFromExisting(existingLog) {
  const goalTaps = {}
  for (const row of existingLog?.goal_entries || []) {
    goalTaps[row.goal_id] = {
      participation: row.participation || '',
      support_level: row.support_level || '',
      achievement: row.achievement || '',
      note: row.note || '',
    }
  }
  const strategyTaps = {}
  for (const row of existingLog?.strategy_events || []) {
    strategyTaps[row.strategy_id] = { response: row.response || '', note: row.note || '' }
  }
  return { goalTaps, strategyTaps }
}

function TapGroup({ label, options, value, onChange }) {
  return (
    <div className="ic-session-evidence__taps">
      <span className="ic-session-log-field__hint">{label}</span>
      <div className="ic-segment" role="group" aria-label={label}>
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={value === opt.value ? 'active' : ''}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export function SubmitSessionLogForm({
  session,
  existingLog = null,
  caseCode,
  childName,
  required = false,
  onSuccess,
  onCancel,
  onCancelSession,
  cancelSessionBusy = false,
  onEditTimes,
}) {
  const isEdit = Boolean(existingLog?.id)
  const isResubmit = isEdit && isLogResubmittable(existingLog)
  const [form, setForm] = useState(emptyLogForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [draftNote, setDraftNote] = useState('')
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const draftTimer = useRef(null)
  const serverAutosaveTimer = useRef(null)
  const [serverAutosaveState, setServerAutosaveState] = useState('idle')
  const [dirtySinceServerSave, setDirtySinceServerSave] = useState(false)
  const [transitionContext, setTransitionContext] = useState(null)
  const [goalItems, setGoalItems] = useState([])
  const [strategyItems, setStrategyItems] = useState([])
  const [goalTaps, setGoalTaps] = useState({})
  const [strategyTaps, setStrategyTaps] = useState({})
  const durationComplianceWarning = useMemo(
    () => getDurationComplianceWarning({
      session,
      log: existingLog,
      attendanceStatus: form.attendance_status,
    }),
    [session, existingLog, form.attendance_status],
  )

  useEffect(() => {
    let cancelled = false
    if (existingLog?.is_transition_log || existingLog?.transition_id) {
      setTransitionContext({
        is_transition_session: true,
        transition_role: existingLog.transition_role,
        transition_day_number: existingLog.transition_day_number,
        transition_day_count: existingLog.transition_day_count,
      })
      return () => {
        cancelled = true
      }
    }
    if (!session?.id) {
      setTransitionContext(null)
      return () => {
        cancelled = true
      }
    }
    apiFetch(`/api/v1/sessions/${session.id}/transition-context`)
      .then((context) => {
        if (!cancelled) {
          setTransitionContext(context?.is_transition_session ? context : null)
        }
      })
      .catch(() => {
        if (!cancelled) setTransitionContext(null)
      })
    return () => {
      cancelled = true
    }
  }, [
    existingLog?.id,
    existingLog?.is_transition_log,
    existingLog?.transition_id,
    existingLog?.transition_role,
    existingLog?.transition_day_number,
    existingLog?.transition_day_count,
    session?.id,
  ])

  useEffect(() => {
    let cancelled = false
    async function hydrate() {
      if (existingLog) {
        setForm(logToFormState(existingLog))
        const taps = tapsFromExisting(existingLog)
        setGoalTaps(taps.goalTaps)
        setStrategyTaps(taps.strategyTaps)
        return
      }
      if (!session?.id) {
        setForm(emptyLogForm)
        return
      }
      const draft = await getLogDraft(session.id)
      if (cancelled) return
      if (draft?.fields) {
        setForm({ ...emptyLogForm, ...draft.fields })
        setDraftNote('Restored from device draft')
        if (draft.fields.goalTaps) setGoalTaps(draft.fields.goalTaps)
        if (draft.fields.strategyTaps) setStrategyTaps(draft.fields.strategyTaps)
      } else {
        setForm(emptyLogForm)
      }
    }
    hydrate()
    return () => {
      cancelled = true
    }
  }, [existingLog?.id, session?.id])

  useEffect(() => {
    if (!ENABLE_STRUCTURED_EVIDENCE) return undefined
    const caseId = session?.case_id || existingLog?.case_id
    if (!caseId) return undefined
    let cancelled = false
    apiFetch(`/api/v1/cases/${caseId}/iep-plan`)
      .then((plan) => {
        if (cancelled) return
        setGoalItems(plan?.goal_items || [])
        setStrategyItems(plan?.strategy_items || [])
      })
      .catch(() => {
        if (cancelled) return
        setGoalItems([])
        setStrategyItems([])
      })
    return () => {
      cancelled = true
    }
  }, [session?.case_id, existingLog?.case_id])

  useEffect(() => {
    let cancelled = false
    async function replayPending() {
      const pending = await listPendingDrafts().catch(() => [])
      for (const draft of pending) {
        if (cancelled || !draft?.sync_payload?.session_id) break
        try {
          await apiFetch('/api/v1/daily-logs', {
            method: 'POST',
            body: JSON.stringify(draft.sync_payload),
          })
          await markDraftSynced(draft.sessionId).catch(() => {})
          await clearLogDraft(draft.sessionId).catch(() => {})
        } catch {
          // Keep pending draft for next retry.
        }
      }
    }
    replayPending()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!session?.id || isEdit) return undefined
    if (draftTimer.current) clearTimeout(draftTimer.current)
    draftTimer.current = setTimeout(() => {
      saveLogDraft(session.id, { ...form, goalTaps, strategyTaps, sync_status: 'local' }).catch(() => {})
      setDraftNote('Saved on this device')
    }, 500)
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current)
    }
  }, [form, goalTaps, strategyTaps, session?.id, isEdit])

  const isLateSession = useMemo(() => {
    if (!session?.scheduled_date) return false
    return session.scheduled_date < todayIsoIST()
  }, [session])

  const editable = !isEdit || canEditLog(existingLog)
  const pendingEdit = isEdit && isLogEditable(existingLog)

  useEffect(() => {
    if (!isEdit || !existingLog?.id || !pendingEdit) return undefined
    if (!dirtySinceServerSave) return undefined
    if (serverAutosaveTimer.current) clearTimeout(serverAutosaveTimer.current)
    serverAutosaveTimer.current = setTimeout(async () => {
      try {
        setServerAutosaveState('saving')
        await apiFetch(`/api/v1/daily-logs/${existingLog.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            ...form,
            late_reason: form.late_reason || undefined,
            ...evidencePayload(goalTaps, strategyTaps),
          }),
        })
        setServerAutosaveState('synced')
        setDirtySinceServerSave(false)
      } catch {
        setServerAutosaveState('retry_pending')
      }
    }, 60_000)
    return () => {
      if (serverAutosaveTimer.current) clearTimeout(serverAutosaveTimer.current)
    }
  }, [isEdit, existingLog?.id, pendingEdit, dirtySinceServerSave, form, goalTaps, strategyTaps])

  async function handleResubmit(e) {
    e.preventDefault()
    if (!existingLog?.id) return
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
        ...evidencePayload(goalTaps, strategyTaps),
      }
      const saved = await apiFetch(`/api/v1/daily-logs/${existingLog.id}/resubmit`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      onSuccess?.(saved)
    } catch (err) {
      setError(err.message || 'Could not resubmit log')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSaveProgress(e) {
    e.preventDefault()
    if (!existingLog?.id) return
    setSubmitting(true)
    setError('')
    try {
      await apiFetch(`/api/v1/daily-logs/${existingLog.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          ...form,
          late_reason: form.late_reason || undefined,
          ...evidencePayload(goalTaps, strategyTaps),
        }),
      })
      setServerAutosaveState('synced')
      setDirtySinceServerSave(false)
      setDraftNote('Progress saved')
    } catch (err) {
      setError(err.message || 'Could not save progress')
    } finally {
      setSubmitting(false)
    }
  }

  const timeRange = formatSessionTimeRange(session)
  const displayName = childName || session?.child_name || caseCode || session?.case_code || 'Client'
  const showBrief = Boolean(session?.actual_end_at || session?.status === 'COMPLETED')

  async function persistLocalDraft(syncStatus = 'local') {
    if (!session?.id || isEdit) return
    await saveLogDraft(session.id, { ...form, goalTaps, strategyTaps, sync_status: syncStatus })
    setDraftNote(syncStatus === 'pending_sync' ? 'Saved on device — will sync when online' : 'Draft saved on this device')
  }

  async function handleSaveDraft() {
    setError('')
    try {
      await persistLocalDraft('local')
    } catch {
      setError('Could not save draft on this device')
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!isEdit && !session?.id) {
      setError('Session is missing — refresh the page and try again.')
      return
    }
    if (!isEdit && session?.status && session.status !== 'COMPLETED') {
      if (session.status === 'SCHEDULED') {
        setError(
          'This visit still needs its session times recorded. Use Forgot to log, enter when the visit happened, then tap Record visit & write log.',
        )
      } else if (session.status === 'IN_PROGRESS') {
        setError('End the live session first — use End session above — then submit this log.')
      } else {
        setError('This visit is not marked finished yet — complete the session before submitting the log.')
      }
      return
    }
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
        ...evidencePayload(goalTaps, strategyTaps),
      }
      let saved
      if (isEdit) {
        saved = await apiFetch(`/api/v1/daily-logs/${existingLog.id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        })
      } else {
        saved = await apiFetch('/api/v1/daily-logs', {
          method: 'POST',
          body: JSON.stringify({ session_id: session.id, ...body }),
        })
      }
      if (session?.id) void clearLogDraft(session.id)
      setDraftNote('')
      onSuccess?.(saved)
    } catch (err) {
      if (session?.id) {
        await saveLogDraft(session.id, {
          ...form,
          goalTaps,
          strategyTaps,
          sync_status: 'pending_sync',
          sync_payload: { session_id: session.id, ...body },
        }).catch(() => {})
        setDraftNote('Saved on device — will sync when you’re back online')
      }
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
      <SessionCancelConfirmDialog
        open={cancelDialogOpen}
        busy={cancelSessionBusy}
        onKeep={() => setCancelDialogOpen(false)}
        onConfirm={async () => {
          if (!onCancelSession) return
          await onCancelSession()
          setCancelDialogOpen(false)
        }}
      />
      <header className="ic-session-log-panel__head">
        <div>
          <p className="ic-session-log-panel__eyebrow">
            {isResubmit
              ? 'Rejected session log'
              : isEdit
                ? 'Edit session log'
                : required
                  ? 'Complete Session Log'
                  : 'Session log'}
          </p>
          <h2 className="ic-session-log-panel__title">
            {isResubmit ? 'Review and resubmit' : isEdit ? 'Update visit details' : 'Complete session log'}
          </h2>
          {required && session?.actual_end_at ? (
            <p className="ic-session-log-panel__meta">
              Session ended at {formatTimeIST(session.actual_end_at)}. Now complete the session log.
            </p>
          ) : (
            <p className="ic-session-log-panel__meta">
              <strong>{displayName}</strong>
              {session?.scheduled_date ? <> · {formatDisplayDate(session.scheduled_date)}</> : null}
              {timeRange ? <> · {timeRange}</> : null}
            </p>
          )}
          {required && session?.actual_end_at ? (
            <p className="ic-session-log-panel__meta">
              <strong>{displayName}</strong>
              {session?.scheduled_date ? <> · {formatDisplayDate(session.scheduled_date)}</> : null}
              {timeRange ? <> · {timeRange}</> : null}
            </p>
          ) : null}
        </div>
        {!required && onCancel ? (
          <button type="button" className="ic-btn ic-btn--ghost ic-session-log-panel__dismiss" onClick={onCancel}>
            Close
          </button>
        ) : null}
      </header>

      {transitionContext ? (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--transition" role="status">
          <strong>
            Transition day {transitionContext.transition_day_number || '—'} of{' '}
            {transitionContext.transition_day_count || 3}
          </strong>
          {' · '}
          You are the {transitionContext.transition_role || 'participating'} therapist. This log will be recorded as a
          transition log.
        </p>
      ) : null}

      {showBrief ? (
        <SessionBrief
          session={session}
          childName={childName}
          caseCode={caseCode}
          log={existingLog}
          onEditTimes={onEditTimes}
        />
      ) : null}

      {session?.auto_ended ? (
        <div className="ic-session-log-panel__banner ic-session-log-panel__banner--warn" style={{ borderLeft: '4px solid #f59e0b', backgroundColor: '#fffbeb', color: '#b45309', padding: '12px', margin: '0 0 16px 0', borderRadius: '4px' }}>
          This session was auto-ended because it exceeded the expected duration. Please review actual start/end time before submitting the daily log.{' '}
          {onEditTimes ? (
            <button type="button" className="ic-btn ic-btn--link" onClick={onEditTimes} style={{ textDecoration: 'underline', cursor: 'pointer', padding: 0, border: 'none', background: 'none', color: '#d97706', fontWeight: 'bold' }}>
              Edit times
            </button>
          ) : null}
        </div>
      ) : null}

      {durationComplianceWarning ? (
        <div className="ic-session-log-panel__banner ic-session-log-panel__banner--warn" role="status">
          {durationComplianceWarning.message}{' '}
          {onEditTimes ? (
            <button type="button" className="ic-btn ic-btn--link" onClick={onEditTimes}>
              Edit times
            </button>
          ) : null}
        </div>
      ) : null}

      {isResubmit && existingLog?.review_note ? (
        <div className="ic-session-log-panel__banner ic-session-log-panel__banner--warn">
          <strong>Rejection feedback:</strong> {existingLog.review_note}
        </div>
      ) : null}

      {required ? (
        <p className="ic-session-log-panel__banner">
          Your timer has stopped. Review the session summary above, then submit this log so the visit is recorded. Use{' '}
          <strong>Save draft</strong> if you need to step away — the visit stays in <strong>Needs log</strong> until you
          submit.
        </p>
      ) : isResubmit ? (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          Update the log based on the feedback above. You can edit session times if needed, then resubmit for review.
        </p>
      ) : isEdit ? (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          Use Save Draft to save without submitting.
        </p>
      ) : (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          Capture what happened while it is fresh. Family-facing notes are shared after admin review.
        </p>
      )}

      {error ? <p className="ic-session-log-panel__error">{error}</p> : null}

      {isLateSession && (!isEdit || isResubmit) ? (
        <p className="ic-session-log-panel__late-banner">
          This visit is from a past day. You must add a <strong>late reason</strong> below before admin can approve
          the log.
        </p>
      ) : null}

      <form className="ic-session-log-form" onSubmit={isResubmit ? handleResubmit : handleSubmit}>
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
                onChange={(e) => {
                  setForm({ ...form, [key]: e.target.value })
                  setDirtySinceServerSave(true)
                }}
                rows={rows}
                required={fieldRequired}
              />
            </label>
          ))}
        </div>

        {ENABLE_STRUCTURED_EVIDENCE && (goalItems.length > 0 || strategyItems.length > 0) ? (
          <section className="ic-session-evidence" aria-label="Session evidence">
            {goalItems.length > 0 ? (
              <div className="ic-session-evidence__block">
                <h3 className="ic-session-evidence__title">IEP goals this session</h3>
                <p className="ic-session-log-field__hint">Tap how the child participated, the support used, and what showed up. Notes are optional.</p>
                {goalItems.map((item) => {
                  const taps = goalTaps[item.id] || {}
                  const patch = (key, value) => {
                    setGoalTaps((prev) => ({ ...prev, [item.id]: { ...prev[item.id], [key]: value } }))
                    setDirtySinceServerSave(true)
                  }
                  return (
                    <article key={item.id} className="ic-session-evidence__card">
                      <p className="ic-session-evidence__statement">{item.statement}</p>
                      <TapGroup label="Participation" options={PARTICIPATION_OPTS} value={taps.participation} onChange={(v) => patch('participation', v)} />
                      <TapGroup label="Support" options={SUPPORT_OPTS} value={taps.support_level} onChange={(v) => patch('support_level', v)} />
                      <TapGroup label="What showed up" options={ACHIEVEMENT_OPTS} value={taps.achievement} onChange={(v) => patch('achievement', v)} />
                      <label className="ic-session-log-field">
                        <span className="ic-session-log-field__hint">Note (optional)</span>
                        <textarea
                          rows={2}
                          value={taps.note || ''}
                          onChange={(e) => patch('note', e.target.value)}
                        />
                      </label>
                    </article>
                  )
                })}
              </div>
            ) : null}
            {strategyItems.length > 0 ? (
              <div className="ic-session-evidence__block">
                <h3 className="ic-session-evidence__title">Strategies used</h3>
                <p className="ic-session-log-field__hint">How did this strategy land today?</p>
                {strategyItems.map((item) => {
                  const taps = strategyTaps[item.id] || {}
                  const patch = (key, value) => {
                    setStrategyTaps((prev) => ({ ...prev, [item.id]: { ...prev[item.id], [key]: value } }))
                    setDirtySinceServerSave(true)
                  }
                  return (
                    <article key={item.id} className="ic-session-evidence__card">
                      <p className="ic-session-evidence__statement">{item.statement}</p>
                      <TapGroup label="Response" options={STRATEGY_OPTS} value={taps.response} onChange={(v) => patch('response', v)} />
                      <label className="ic-session-log-field">
                        <span className="ic-session-log-field__hint">Note (optional)</span>
                        <textarea
                          rows={2}
                          value={taps.note || ''}
                          onChange={(e) => patch('note', e.target.value)}
                        />
                      </label>
                    </article>
                  )
                })}
              </div>
            ) : null}
          </section>
        ) : null}

        {isLateSession ? (
          <label className="ic-session-log-field ic-session-log-field--warn">
            <span className="ic-session-log-field__label">
              Late reason
              <span className="ic-session-log-field__req">Required</span>
            </span>
            <span className="ic-session-log-field__hint">
              Scheduled {formatDisplayDate(session?.scheduled_date)} — explain why the log is late (required to save).
            </span>
            <textarea
              required
              value={form.late_reason}
              onChange={(e) => {
                setForm({ ...form, late_reason: e.target.value })
                setDirtySinceServerSave(true)
              }}
              rows={3}
              placeholder="e.g. Session completed offline; submitting after travel."
            />
          </label>
        ) : null}

        {draftNote ? <p className="ic-draft-badge">{draftNote}</p> : null}

        <div className="ic-session-log-form__actions">
          {isResubmit ? (
            <>
              <button type="submit" className="ic-btn ic-btn--primary ic-session-log-form__submit" disabled={submitting}>
                {submitting ? 'Submitting…' : 'Resubmit for review'}
              </button>
              <button
                type="button"
                className="ic-btn ic-btn--ghost"
                disabled={submitting}
                onClick={handleSaveProgress}
              >
                Save progress
              </button>
            </>
          ) : isEdit ? (
            <>
              <button type="submit" className="ic-btn ic-btn--primary ic-session-log-form__submit" disabled={submitting}>
                {submitting ? 'Submitting…' : 'Submit log'}
              </button>
              <button
                type="button"
                className="ic-btn ic-btn--ghost"
                disabled={submitting}
                onClick={handleSaveProgress}
              >
                Save draft
              </button>
            </>
          ) : (
            <button type="submit" className="ic-btn ic-btn--primary ic-session-log-form__submit" disabled={submitting}>
              {submitting ? 'Saving…' : 'Submit log & finish'}
            </button>
          )}
          {!isEdit && session?.id ? (
            <button type="button" className="ic-btn ic-btn--ghost" disabled={submitting} onClick={handleSaveDraft}>
              Save draft
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
            The visit is already ended on the clock. Submit the log when you can — drafts are stored on this device only
            until you submit.
          </p>
        ) : null}
        {required && !isEdit && onCancelSession ? (
          <button
            type="button"
            className="ic-session-log-mistake-cancel"
            disabled={submitting || cancelSessionBusy}
            onClick={() => setCancelDialogOpen(true)}
          >
            Started by mistake? Cancel this session
          </button>
        ) : null}
        {isEdit && pendingEdit ? (
          <p className="ic-session-log-form__footnote">
            {serverAutosaveState === 'saving'
              ? 'Saving…'
              : serverAutosaveState === 'retry_pending'
                ? 'Saved locally. Retry pending.'
                : serverAutosaveState === 'synced'
                  ? 'Synced'
                  : 'Saved locally'}
          </p>
        ) : null}
      </form>
    </div>
  )
}
