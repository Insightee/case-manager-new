import { useEffect, useState } from 'react'

/**
 * Lightweight confirm + optional note for ticket/incident lifecycle actions.
 */
export function TicketFlowDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  requireNote = false,
  noteLabel = 'Note',
  notePlaceholder = '',
  initialNote = '',
  danger = false,
  onConfirm,
  onCancel,
}) {
  const [note, setNote] = useState(initialNote)

  useEffect(() => {
    if (open) setNote(initialNote)
  }, [open, initialNote])

  if (!open) return null

  const noteOk = !requireNote || note.trim().length >= 3

  return (
    <div
      className="ticket-flow-dialog__backdrop"
      role="presentation"
      onClick={onCancel}
      onKeyDown={(e) => e.key === 'Escape' && onCancel?.()}
    >
      <div
        className="ticket-flow-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ticket-flow-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="ticket-flow-dialog-title" className="ticket-flow-dialog__title">
          {title}
        </h3>
        {description ? <p className="ticket-flow-dialog__desc">{description}</p> : null}
        <label className="ticket-flow-dialog__label">
          {noteLabel}
          <textarea
            className="ticket-flow-dialog__input"
            rows={3}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={notePlaceholder}
          />
        </label>
        {requireNote && !noteOk ? (
          <p className="ticket-flow-dialog__hint">Please enter at least 3 characters.</p>
        ) : null}
        <div className="ticket-flow-dialog__actions">
          <button type="button" className="admin-btn admin-btn--ghost" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? 'admin-btn admin-btn--danger' : 'admin-btn admin-btn--primary'}
            disabled={!noteOk}
            onClick={() => onConfirm?.(note.trim() || undefined)}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
