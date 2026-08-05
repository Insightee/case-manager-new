import { todayIsoIST } from './datetime.js'

/**
 * @typedef {'START_SESSION'|'CONTINUE_SESSION'|'COMPLETE_LOG'|'EDIT_LOG'|'VIEW_EXISTING'|'REQUEST_ADDITIONAL_VISIT'|'DUPLICATE_SAME_DAY'} RecommendedAction
 */

export function canStartSessionToday(session) {
  if (!session?.scheduled_date) return { ok: true }
  const today = todayIsoIST()
  if (session.scheduled_date > today) {
    return {
      ok: false,
      reason: 'future',
      message:
        'This visit is scheduled for a later date. Start is only available on the day of the visit. Use Forgot to log after the visit if you missed clocking in.',
    }
  }
  if (session.scheduled_date < today) {
    return {
      ok: false,
      reason: 'past',
      message:
        'This visit was scheduled for another day. Use Forgot to log to record it.',
    }
  }
  return { ok: true }
}

export function sessionStartIdempotencyKey(therapistId, session) {
  const slotPart = session?.slot_id ?? session?.id ?? 'x'
  return `${therapistId}-${slotPart}-${session?.scheduled_date ?? todayIsoIST()}`
}

/**
 * @param {import('./apiClient.js').ApiErrorDetail | string | undefined} detail
 */
export function parseSessionStartConflict(detail) {
  if (!detail || typeof detail === 'string') return null
  if (detail.existing_session_id && detail.recommended_action) {
    return {
      existingSessionId: detail.existing_session_id,
      recommendedAction: detail.recommended_action,
      message: detail.message || 'A session already exists for this visit.',
      currentStatus: detail.current_status,
    }
  }
  return null
}

/** @param {RecommendedAction} action */
export function labelForSessionAction(action, { hasDraft = false } = {}) {
  switch (action) {
    case 'CONTINUE_SESSION':
      return 'Continue session'
    case 'COMPLETE_LOG':
      return 'Edit session log'
    case 'EDIT_LOG':
      return hasDraft ? 'Continue log' : 'Edit existing log'
    case 'VIEW_EXISTING':
      return 'View submitted log'
    case 'REQUEST_ADDITIONAL_VISIT':
      return 'Record additional visit'
    case 'DUPLICATE_SAME_DAY':
      return 'Start another session today'
    default:
      return 'Start session'
  }
}

export function logsPathForSession(sessionId) {
  return `/therapist/logs?session=${sessionId}`
}

/** @param {import('./apiClient.js').ApiErrorDetail | string | undefined} detail */
export function parseChildAbsenceBlock(detail) {
  if (!detail || typeof detail === 'string') return null
  if (detail.code === 'PENDING_CHILD_ABSENCE' || detail.code === 'CHILD_MARKED_ABSENT') {
    return {
      code: detail.code,
      message: detail.message || 'Session cannot be started because of child absence.',
    }
  }
  return null
}

/** @param {import('./apiClient.js').ApiErrorDetail | string | undefined} detail */
export function isAbsenceConflict(detail) {
  if (!detail || typeof detail === 'string') return false
  return (
    detail.code === 'PENDING_CHILD_ABSENCE' ||
    detail.code === 'CHILD_MARKED_ABSENT' ||
    detail.recommended_action === 'blocked_absence'
  )
}

/** @param {import('./apiClient.js').ApiErrorDetail | string | undefined} detail */
export function parsePendingLogBlock(detail) {
  if (!detail || typeof detail === 'string') return null
  if (detail.code === 'PENDING_LOG_REQUIRED') {
    return {
      code: detail.code,
      blockingSessionId: detail.blocking_session_id || detail.existing_session_id,
      message: detail.message,
      canDiscard: detail.can_discard !== false,
    }
  }
  return null
}

/** @param {import('./apiClient.js').ApiErrorDetail | string | undefined} detail */
export function isPendingLogBlock(detail) {
  return parsePendingLogBlock(detail) != null
}

/** @param {import('./apiClient.js').ApiErrorDetail | string | undefined} detail */
export function isSameDayDuplicateConflict(detail) {
  const conflict = parseSessionStartConflict(detail)
  return conflict?.recommendedAction === 'DUPLICATE_SAME_DAY'
}

/** @param {Array<{ id?: number, case_id?: number, scheduled_date?: string }>} needsLogSessions */
export function blockingLogByCase(needsLogSessions) {
  /** @type {Record<number, object>} */
  const map = {}
  for (const s of needsLogSessions || []) {
    const cid = s?.case_id
    if (cid != null && map[cid] == null) map[cid] = s
  }
  return map
}

/** @param {Array<{ id?: number, case_id?: number }>} needsLogSessions */
export function getBlockingLogForCase(needsLogSessions, caseId) {
  if (caseId == null) return null
  return blockingLogByCase(needsLogSessions)[caseId] || null
}
