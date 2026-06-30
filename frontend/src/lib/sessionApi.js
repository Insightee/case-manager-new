import { apiFetch } from './apiClient.js'
import {
  labelForSessionAction,
  logsPathForSession,
  parseChildAbsenceBlock,
  parseSessionStartConflict,
  sessionStartIdempotencyKey,
} from './sessionStartRules.js'

/**
 * Start a clinical session with idempotency and conflict handling.
 * @returns {Promise<{ ok: true, session: object } | { ok: false, conflict: object, message: string }>}
 */
export async function startClinicalSession(sessionId, session, therapistId, body = {}) {
  const key = sessionStartIdempotencyKey(therapistId, { ...session, id: sessionId })
  try {
    const started = await apiFetch(`/api/v1/sessions/${sessionId}/start`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: { 'Idempotency-Key': key },
    })
    return { ok: true, session: started }
  } catch (err) {
    if (err?.status === 400) {
      const block = parseChildAbsenceBlock(err.detail)
      if (block) {
        return { ok: false, absenceBlock: block, message: block.message }
      }
    }
    if (err?.status === 409) {
      const conflict = parseSessionStartConflict(err.detail)
      if (conflict) {
        return { ok: false, conflict, message: conflict.message }
      }
    }
    throw err
  }
}

/** Navigate therapist to the right screen when start hits an existing visit. */
export function redirectForSessionConflict(conflict, navigate) {
  if (!conflict?.existingSessionId) return
  const path = logsPathForSession(conflict.existingSessionId)
  navigate(path)
}

export { labelForSessionAction, logsPathForSession }
