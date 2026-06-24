import { isLogEditable, isLogResubmittable } from './sessionLogUtils.js'
import { existingVisitForDay } from './sessionDayConflict.js'

/**
 * Decide how to open a session from ?session= deep links or schedule taps.
 */
export function resolveSessionDeepLink(session, logs = [], context = {}) {
  if (!session?.id) {
    return { type: 'error', message: 'Session not found' }
  }

  if (session.status === 'SCHEDULED') {
    const existing = existingVisitForDay(session, context)
    if (existing) {
      return resolveSessionDeepLink(existing, logs, context)
    }
    return { type: 'visit', session }
  }

  if (session.status === 'IN_PROGRESS') {
    return { type: 'visit', session }
  }

  if (session.status === 'COMPLETED' && !session.has_daily_log) {
    return { type: 'log', session, required: true }
  }

  const log = logs.find((l) => Number(l.session_id) === Number(session.id) && l.id > 0)
  if (log) {
    if (log.approval_status === 'PENDING' && isLogEditable(log)) {
      return { type: 'log', session, log, required: false }
    }
    if (isLogResubmittable(log)) {
      return { type: 'log', session, log, required: false }
    }
    if (session.has_daily_log) {
      return { type: 'log', session, log, required: false }
    }
    return { type: 'readonly', session, log }
  }

  if (session.status === 'COMPLETED' && session.has_daily_log) {
    return { type: 'log', session, required: false, fetchLog: true }
  }

  return { type: 'visit', session }
}
