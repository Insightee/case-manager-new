import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import './admin-client-status.css'

/**
 * Modal to close a case with required reason + termination date.
 * Posts to /client-status (not bare PATCH).
 */
export function CaseCloseModal({ caseId, caseCode, onClose, onSuccess }) {
  const [effectiveDate, setEffectiveDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit() {
    if (!effectiveDate || reason.trim().length < 5) {
      setError('Looks like we still need a termination date and a reason (at least 5 characters).')
      return
    }
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/cases/${caseId}/client-status`, {
        method: 'POST',
        body: JSON.stringify({
          new_status: 'CLOSED',
          effective_date: effectiveDate,
          reason: reason.trim(),
          internal_notes: notes.trim() || null,
        }),
      })
      onSuccess?.(result)
      onClose?.()
    } catch (err) {
      setError(err.message || 'Could not close this case right now. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="cs-modal-overlay" onClick={onClose}>
      <div className="cs-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="case-close-title">
        <p className="cs-modal__title" id="case-close-title">
          Close case{caseCode ? ` ${caseCode}` : ''}
        </p>

        {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

        <div className="admin-form-grid" style={{ maxWidth: '100%' }}>
          <label className="admin-label">
            Termination date <span style={{ color: '#ef4444' }}>*</span>
            <input
              type="date"
              className="admin-input"
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
            />
          </label>

          <label className="admin-label" style={{ gridColumn: '1 / -1' }}>
            Reason for closing <span style={{ color: '#ef4444' }}>*</span>
            <textarea
              className="admin-input"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is this case being closed?"
            />
          </label>

          <label className="admin-label" style={{ gridColumn: '1 / -1' }}>
            Internal notes (optional)
            <textarea
              className="admin-input"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Additional context for the admin team"
            />
          </label>
        </div>

        <div className="cs-modal__impact">
          <strong>What happens next:</strong>
          <br />
          Final billing uses the termination date. Future sessions are cancelled and the therapist
          assignment ends. Records stay accessible. Reopening later will require a new therapist
          assignment.
        </div>

        <div className="cs-modal__actions">
          <button type="button" className="admin-btn admin-btn--ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--primary"
            onClick={handleSubmit}
            disabled={saving || !effectiveDate || reason.trim().length < 5}
          >
            {saving ? 'Closing…' : 'Close case'}
          </button>
        </div>
      </div>
    </div>
  )
}
