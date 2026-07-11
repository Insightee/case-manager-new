/** @deprecated Use VoiceSessionLogFlow — see docs/product/SESSION_LOG_V1.md */
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
import { SessionBrief } from './SessionBrief.jsx'
import { SessionLogGoalTracker } from '../clinical/SessionLogGoalTracker.jsx'
import {
  SessionLogEvidencePanel,
  sessionEvidenceHasPayload,
  buildActivitiesDoneFromEvidence,
  prepareEvidenceForSubmit,
} from '../clinical/session-log/SessionLogEvidencePanel.jsx'
import { validateSessionEvidenceQuickFields } from '../../lib/clinicalScoring.js'
import { SessionLogV2Chrome } from '../clinical/session-log/SessionLogV2Chrome.jsx'
import { SessionLogNotesDual } from '../clinical/session-log/SessionLogNotesDual.jsx'
import { SessionLogParentPreview } from '../clinical/session-log/SessionLogParentPreview.jsx'
import { SessionLogEvidenceUpload } from '../clinical/session-log/SessionLogEvidenceUpload.jsx'
import { SessionLogAiAssist } from '../clinical/SessionLogAiAssist.jsx'
import { GOALS_STRATEGIES_ENGINE_V2, STRUCTURED_SESSION_EVIDENCE } from '../../lib/reportsRevampFlags.js'
import { goalHasSessionWork } from '../../lib/clinicalScoring.js'
import { ClinicalVisibilityBadge } from '../clinical-ui/ClinicalVisibilityBadge.jsx'
import { SessionCancelConfirmDialog } from './SessionCancelConfirmDialog.jsx'
import '../../styles/goals-strategies-engine.css'
import '../../styles/session-log-v2.css'

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
  const [sessionEvidence, setSessionEvidence] = useState(null)
  const [legacyEvidenceSchema, setLegacyEvidenceSchema] = useState(null)
  const [sessionSnapshot, setSessionSnapshot] = useState(session)
  const [evidenceUploads, setEvidenceUploads] = useState([])
  const [parentVoiceAttachment, setParentVoiceAttachment] = useState(null)
  const [showEvidenceNudges, setShowEvidenceNudges] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function loadEvidenceSchema() {
      if (!GOALS_STRATEGIES_ENGINE_V2 || !existingLog?.id) {
        setLegacyEvidenceSchema(null)
        return
      }
      try {
        const evidence = await apiFetch(`/api/v1/daily-logs/${existingLog.id}/session-evidence`)
        if (cancelled) return
        setLegacyEvidenceSchema(evidence?.schema_version ?? null)
        if (evidence?.schema_version === 2) {
          setSessionEvidence({
            schema_version: 2,
            goals: evidence.goals || [],
            strategies: evidence.strategies || [],
          })
        }
      } catch {
        if (!cancelled) setLegacyEvidenceSchema(null)
      }
    }
    loadEvidenceSchema()
    return () => {
      cancelled = true
    }
  }, [existingLog?.id])

  useEffect(() => {
    setSessionSnapshot(session)
  }, [session?.id, session?.actual_start_at, session?.actual_end_at, session?.edited_start_at, session?.edited_end_at])

  useEffect(() => {
    let cancelled = false
    async function hydrate() {
      if (existingLog) {
        setForm(logToFormState(existingLog))
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
      saveLogDraft(session.id, { ...form, sync_status: 'local' }).catch(() => {})
      setDraftNote('Saved on this device')
    }, 500)
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current)
    }
  }, [form, session?.id, isEdit])

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
  }, [isEdit, existingLog?.id, pendingEdit, dirtySinceServerSave, form])

  async function handleResubmit(e) {
    e.preventDefault()
    if (!existingLog?.id) return
    const validationError = validateSessionLogForm(
      useV2EvidenceEngine ? formBodyForSubmit() : form,
      { isLateSession },
    )
    if (validationError) {
      setError(validationError)
      return
    }
    if (useV2EvidenceEngine) {
      const evidenceMsg = validateSessionEvidenceQuickFields(sessionEvidence)
      if (evidenceMsg) {
        setShowEvidenceNudges(true)
        setError(evidenceMsg)
        return
      }
    }
    setSubmitting(true)
    setError('')
    try {
      const body = formBodyForSubmit()
      const evidencePayload = evidencePayloadForSubmit()
      if (evidencePayload) body.session_evidence = evidencePayload
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

  const useV2EvidenceEngine =
    GOALS_STRATEGIES_ENGINE_V2 && session?.case_id && legacyEvidenceSchema !== 1
  const showLegacyGoalTracker =
    STRUCTURED_SESSION_EVIDENCE &&
    existingLog?.id &&
    session?.case_id &&
    (!GOALS_STRATEGIES_ENGINE_V2 || legacyEvidenceSchema === 1)

  function evidencePayloadForSubmit() {
    if (!useV2EvidenceEngine || !sessionEvidenceHasPayload(sessionEvidence)) return undefined
    const prepared = prepareEvidenceForSubmit(sessionEvidence)
    return {
      goals: (prepared.goals || []).map(({ id: _id, schema_version: _sv, activity_phases: _ap, ...g }) => ({
        ...g,
        schema_version: 2,
      })),
      strategies: prepared.strategies || [],
    }
  }

  function formBodyForSubmit() {
    const body = {
      ...form,
      late_reason: form.late_reason || undefined,
    }
    if (useV2EvidenceEngine) {
      const autoActivities = buildActivitiesDoneFromEvidence(sessionEvidence)
      if (autoActivities && (!body.activities_done || body.activities_done.trim().length < 3)) {
        body.activities_done = autoActivities
      }
      if (!body.goals_addressed?.trim() && sessionEvidence?.goals?.length) {
        body.goals_addressed = sessionEvidence.goals
          .filter(goalHasSessionWork)
          .map((g) => g.goal_label)
          .filter(Boolean)
          .join('; ')
      }
    }
    return body
  }

  async function persistLocalDraft(syncStatus = 'local') {
    if (!session?.id || isEdit) return
    await saveLogDraft(session.id, { ...form, sync_status: syncStatus })
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
      setError('End the session before submitting a log.')
      return
    }
    const validationError = validateSessionLogForm(
      useV2EvidenceEngine ? formBodyForSubmit() : form,
      { isLateSession },
    )
    if (validationError) {
      setError(validationError)
      return
    }
    if (useV2EvidenceEngine) {
      const evidenceMsg = validateSessionEvidenceQuickFields(sessionEvidence)
      if (evidenceMsg) {
        setShowEvidenceNudges(true)
        setError(evidenceMsg)
        return
      }
    }
    setSubmitting(true)
    setError('')
    try {
      const body = formBodyForSubmit()
      const evidencePayload = evidencePayloadForSubmit()
      if (evidencePayload) body.session_evidence = evidencePayload
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

  function handleNotesChange(partial) {
    setForm((prev) => ({ ...prev, ...partial }))
    setDirtySinceServerSave(true)
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

  if (useV2EvidenceEngine) {
    return (
      <div className={`gs-engine ic-session-log-panel ic-session-log-panel--v2${required ? ' ic-session-log-panel--required' : ''}`}>
        <SessionLogV2Chrome
          session={sessionSnapshot}
          caseCode={caseCode}
          childName={childName}
          sessionEvidence={sessionEvidence}
          log={existingLog}
          onTimesUpdated={(updated) => setSessionSnapshot((prev) => ({ ...prev, ...updated }))}
        />

        {isResubmit && existingLog?.review_note ? (
          <div className="ic-session-log-panel__banner ic-session-log-panel__banner--warn sl-v2-body" style={{ paddingTop: 0 }}>
            <strong>Rejection feedback:</strong> {existingLog.review_note}
          </div>
        ) : null}

        {error ? (
          <p className="ic-session-log-panel__error sl-v2-body" style={{ paddingTop: 0, margin: 0 }}>
            {error}
          </p>
        ) : null}

        <form className="ic-session-log-form" onSubmit={isResubmit ? handleResubmit : handleSubmit}>
          <div className="sl-v2-body">
            <SessionLogEvidencePanel
              caseId={session.case_id}
              logId={existingLog?.id}
              sessionId={session?.id}
              environment={session?.mode}
              value={sessionEvidence}
              onChange={setSessionEvidence}
              readOnly={isEdit && !pendingEdit}
              showNudges={showEvidenceNudges}
            />

            <SessionLogNotesDual
              form={form}
              onChange={handleNotesChange}
              readOnly={isEdit && !pendingEdit}
              caseId={session?.case_id}
              sessionDate={session?.scheduled_date}
              voiceAttachment={parentVoiceAttachment}
              onVoiceAttachmentChange={setParentVoiceAttachment}
            />

            <SessionLogEvidenceUpload
              caseId={session?.case_id}
              sessionDate={session?.scheduled_date}
              readOnly={isEdit && !pendingEdit}
              uploads={evidenceUploads}
              onChange={setEvidenceUploads}
            />

            {isLateSession ? (
              <div className="sl-late-reason-block">
                <p className="sl-late-banner" role="status">
                  Past-day visit: add a late reason before submitting.
                </p>
                <label className="gs-field ic-session-log-field--warn">
                  <span className="gs-field__label">
                    Late reason
                    <span className="ic-session-log-field__req">Required</span>
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
              </div>
            ) : null}

            {draftNote ? <p className="ic-draft-badge">{draftNote}</p> : null}
          </div>

          <div className="sl-v2-footer-preview">
            <SessionLogParentPreview sessionEvidence={sessionEvidence} parentNotes={form.parent_notes} />
          </div>

          <div className="sl-v2-footer">
            {!isEdit && session?.id ? (
              <button type="button" className="gs-btn gs-btn--ghost" disabled={submitting} onClick={handleSaveDraft}>
                Save Draft
              </button>
            ) : isEdit && pendingEdit ? (
              <button type="button" className="gs-btn gs-btn--ghost" disabled={submitting} onClick={handleSaveProgress}>
                Save Draft
              </button>
            ) : null}
            {!required && onCancel ? (
              <button type="button" className="gs-btn gs-btn--ghost" disabled={submitting} onClick={onCancel}>
                Cancel
              </button>
            ) : null}
            <button type="submit" className="gs-btn gs-btn--primary sl-v2-footer__submit" disabled={submitting}>
              {submitting
                ? 'Saving…'
                : isResubmit
                  ? 'Resubmit for review'
                  : 'Submit log'}
            </button>
          </div>
        </form>
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

      <form className="ic-session-log-form" onSubmit={isResubmit ? handleResubmit : handleSubmit}>
        <div className="ic-session-log-form__grid">
          {FIELDS.map(({ key, label, hint, rows, highlight, required: fieldRequired }) => {
            const isParentField   = key === 'parent_notes'
            const isInternalField = key === 'session_notes' || key === 'observations'
            return (
              <label
                key={key}
                className={`ic-session-log-field${highlight ? ' ic-session-log-field--highlight' : ''}`}
              >
                <span className="ic-session-log-field__label" style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', flexWrap: 'wrap' }}>
                  {label}
                  {fieldRequired ? <span className="ic-session-log-field__req">Required</span> : null}
                  {isParentField   ? <ClinicalVisibilityBadge visibility="parent"   /> : null}
                  {isInternalField ? <ClinicalVisibilityBadge visibility="internal" /> : null}
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
            )
          })}
        </div>

        {useV2EvidenceEngine ? (
          <SessionLogEvidencePanel
            caseId={session.case_id}
            logId={existingLog?.id}
            sessionId={session?.id}
            environment={session?.mode}
            value={sessionEvidence}
            onChange={setSessionEvidence}
            readOnly={isEdit && !pendingEdit}
            showNudges={showEvidenceNudges}
          />
        ) : null}

        {isEdit && existingLog?.id ? (
          <SessionLogAiAssist
            logId={existingLog.id}
            note={form.session_notes}
            onImprovedNote={(text) => setForm((prev) => ({ ...prev, session_notes: text }))}
          />
        ) : null}

        {isLateSession ? (
          <div className="sl-late-reason-block">
            <p className="sl-late-banner" role="status">
              Past-day visit: add a late reason before submitting.
            </p>
            <label className="ic-session-log-field ic-session-log-field--warn">
              <span className="ic-session-log-field__label">
                Late reason
                <span className="ic-session-log-field__req">Required</span>
              </span>
              <span className="ic-session-log-field__hint">
                Scheduled {formatDisplayDate(session?.scheduled_date)} — explain why the log is late.
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
          </div>
        ) : null}

        {draftNote ? <p className="ic-draft-badge">{draftNote}</p> : null}

        <div className="ic-session-log-form__actions cp-builder-sticky-actions">
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
      {showLegacyGoalTracker ? (
        <SessionLogGoalTracker logId={existingLog.id} caseId={session.case_id} />
      ) : null}
    </div>
  )
}
