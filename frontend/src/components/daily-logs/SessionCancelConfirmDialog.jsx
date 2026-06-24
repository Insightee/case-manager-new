/**
 * Confirm cancel when therapist started a session by mistake (log screen only).
 */
export function SessionCancelConfirmDialog({ open, busy, onKeep, onConfirm }) {
  if (!open) return null

  return (
    <div className="ic-case-status-modal" role="dialog" aria-modal="true" aria-labelledby="cancel-session-title">
      <button type="button" className="ic-case-status-modal__backdrop" aria-label="Close" onClick={onKeep} />
      <div className="ic-case-status-modal__sheet">
        <h2 id="cancel-session-title">Cancel this session?</h2>
        <p className="ic-case-panel__hint">
          Use this only if the session was started by mistake and no session happened. This will remove the
          active timer and mark the session as cancelled.
        </p>
        <div className="ic-case-status-modal__actions" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
          <button type="button" className="ic-btn ic-btn--primary" disabled={busy} onClick={onKeep}>
            Keep Session
          </button>
          <button type="button" className="ic-btn ic-btn--danger" disabled={busy} onClick={onConfirm}>
            {busy ? 'Cancelling…' : 'Cancel Session'}
          </button>
        </div>
      </div>
    </div>
  )
}
