import { isLogEditable } from './sessionLogUtils.js'

/**
 * Decide how to open a session from ?session= deep links or schedule taps.
 */
export function resolveSessionDeepLink(session, logs = []) {
  if (!session?.id) {
    return { type: 'error', message: 'Session not found' }
  }

  if (session.status === 'COMPLETED' && !session.has_daily_log) {
    return { type: 'log', session, required: true }
  }

  if (session.status === 'SCHEDULED' || session.status === 'IN_PROGRESS') {
    return { type: 'visit', session }
  }

  const log = logs.find((l) => Number(l.session_id) === Number(session.id))
  if (log) {
    if (log.approval_status === 'PENDING' && isLogEditable(log)) {
      return { type: 'log', session, log, required: false }
    }
    return { type: 'readonly', session, log }
  }

  return { type: 'visit', session }
}
