/** Inline finance mutation feedback (aria-live). */
export function BillingActionAlert({ error, successMessage, onDismiss }) {
  if (!error && !successMessage) return null
  return (
    <div style={{ marginTop: 8, marginBottom: 8 }}>
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {successMessage || error}
      </span>
      {error ? (
        <div className="admin-alert admin-alert--danger" role="alert">
          {error}
          {onDismiss ? (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginLeft: 8 }} onClick={onDismiss}>
              Dismiss
            </button>
          ) : null}
        </div>
      ) : null}
      {successMessage ? (
        <div className="admin-alert admin-alert--success" role="status">
          {successMessage}
        </div>
      ) : null}
    </div>
  )
}
