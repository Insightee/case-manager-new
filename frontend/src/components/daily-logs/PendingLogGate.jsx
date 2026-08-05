import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate, formatSessionActualRange } from '../../lib/datetime.js'
import { clearLogDraft } from '../../lib/logDraftStore.js'

/**
 * Banner when the therapist must finish or discard their latest visit log before starting anew.
 */
export function PendingLogGate({
  session,
  draftSaved = false,
  busy = false,
  onCompleteLog,
  onDiscard,
}) {
  if (!session?.id) return null

  const displayName = session.child_name || session.case_code || 'Client'
  const when = formatDisplayDate(session.scheduled_date)
  const timeRange = formatSessionActualRange(session)

  return (
    <section className="ic-pending-log-gate" aria-labelledby="pending-log-gate-title">
      <div className="ic-pending-log-gate__icon" aria-hidden>
        📝
      </div>
      <div className="ic-pending-log-gate__body">
        <h3 id="pending-log-gate-title" className="ic-pending-log-gate__title">
          One visit still needs a log
        </h3>
        <p className="ic-pending-log-gate__text">
          Before you start another session for this client, finish the log for{' '}
          <strong>{displayName}</strong>
          {when ? ` on ${when}` : ''}
          {timeRange ? ` (${timeRange})` : ''}.
          {draftSaved ? ' You have a draft saved on this device.' : ''}
        </p>
        <div className="ic-pending-log-gate__actions">
          <button
            type="button"
            className="ic-btn ic-btn--primary"
            disabled={busy}
            onClick={() => onCompleteLog?.(session)}
          >
            Complete log
          </button>
          <button
            type="button"
            className="ic-btn ic-btn--ghost"
            disabled={busy}
            onClick={() => onDiscard?.(session)}
          >
            Remove draft visit
          </button>
        </div>
      </div>
    </section>
  )
}

export async function discardPendingLogSession(sessionId) {
  return apiFetch(`/api/v1/sessions/${sessionId}/discard-pending-log`, { method: 'POST', body: JSON.stringify({}) })
}

export async function discardPendingLogWithDraft(sessionId) {
  await discardPendingLogSession(sessionId)
  await clearLogDraft(sessionId).catch(() => {})
}
