import { isLogEditable, isLogResubmittable, validateSessionLogForm } from './sessionLogUtils.js'

/** Whether the scheduled visit date is before today in IST (late log). */
export function isSessionLateForSubmit(session, todayIso) {
  if (!session?.scheduled_date || !todayIso) return false
  return session.scheduled_date < todayIso
}

/** True when a failed submit should be queued for offline sync (not validation/auth). */
export function shouldQueueOfflineDraft(err) {
  if (!err) return false
  if (err.isConnectionError) return true
  const msg = String(err.message || '')
  if (msg.startsWith('Request timed out')) return true
  if (/taking longer than expected/i.test(msg)) return true
  if (/appear offline/i.test(msg)) return true
  if (/connection unstable/i.test(msg)) return true
  return false
}

export function isLateReasonApiError(err) {
  const msg = String(err?.message || '')
  return /late reason/i.test(msg)
}

export function isSessionExpiredError(err) {
  if (err?.isAuthError || err?.isAuthSessionError) return true
  // 403 is a business/permission denial on log submit (e.g. "Case access denied" after a
  // handover, view-only, module access) — show the server reason, not "session expired".
  if (err?.status === 401) return true
  return /session expired/i.test(String(err?.message || ''))
}

/** User-facing message after a failed session-log submit. */
export function sessionLogSubmitFailureMessage(err) {
  if (isSessionExpiredError(err)) {
    return 'Session expired — please sign in again. Your notes are saved on this device.'
  }
  return err?.message || 'Could not save log'
}

/** Client-side gates evaluated at submit time (IST), including late reason and 24h edit window. */
export function evaluateSessionLogSubmitReadiness(session, form, todayIso, { isEdit = false, existingLog = null } = {}) {
  const lateNow = isSessionLateForSubmit(session, todayIso)
  if (isEdit && existingLog && !isLogResubmittable(existingLog) && !isLogEditable(existingLog)) {
    return {
      ok: false,
      lateNow,
      error:
        'The 24-hour editing window for this log has closed. Contact your case manager if you need a correction.',
    }
  }
  if (lateNow && !form.late_reason?.trim()) {
    return {
      ok: false,
      lateNow,
      requireLateUi: true,
      error: 'This session is from a previous day. Add a late reason below, then submit again.',
    }
  }
  const validationError = validateSessionLogForm(form, { isLateSession: lateNow })
  if (validationError) {
    return {
      ok: false,
      lateNow,
      requireLateUi: lateNow && !form.late_reason?.trim(),
      error: validationError,
    }
  }
  return { ok: true, lateNow }
}

/** Pure plan for catch-block side effects (tested without React). */
export function planSessionLogSubmitFailureActions(err, { sessionId, hasBody }) {
  const errorMessage = sessionLogSubmitFailureMessage(err)
  const plan = {
    errorMessage,
    saveLocalDraft: false,
    queueOffline: false,
    requireLateUi: isLateReasonApiError(err),
    draftSyncStatus: null,
  }
  if (!sessionId) return plan
  if (isSessionExpiredError(err)) {
    plan.saveLocalDraft = true
    plan.draftSyncStatus = 'local'
    return plan
  }
  if (shouldQueueOfflineDraft(err) && hasBody) {
    plan.queueOffline = true
    plan.saveLocalDraft = true
    plan.draftSyncStatus = 'pending_sync'
  }
  return plan
}
