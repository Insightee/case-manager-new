import { Link } from 'react-router-dom'
import { logsPathForSession } from '../../lib/sessionStartRules.js'

/**
 * Shown when starting a second session for the same client on the same day.
 */
export function SameDaySessionDialog({ open, conflict, busy, onEditExisting, onStartAnother, onClose }) {
  if (!open || !conflict) return null

  const editPath = logsPathForSession(conflict.existingSessionId)

  return (
    <div className="ic-case-status-modal" role="dialog" aria-modal="true" aria-labelledby="same-day-title">
      <button type="button" className="ic-case-status-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="ic-case-status-modal__sheet">
        <h2 id="same-day-title">You already have a visit today for this client</h2>
        <p className="ic-case-panel__hint">
          {conflict.message ||
            'Edit the existing session or start another visit explicitly.'}
        </p>
        <div className="ic-case-status-modal__actions" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
          <button
            type="button"
            className="ic-btn ic-btn--primary"
            disabled={busy}
            onClick={() => onEditExisting?.(conflict.existingSessionId)}
          >
            Edit existing session
          </button>
          <Link to={editPath} className="ic-btn ic-btn--ghost" onClick={onClose}>
            Open existing log
          </Link>
          <button
            type="button"
            className="ic-btn ic-btn--ghost"
            disabled={busy}
            onClick={onStartAnother}
          >
            {busy ? 'Starting…' : 'Start another session'}
          </button>
          <button type="button" className="ic-btn ic-btn--ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
