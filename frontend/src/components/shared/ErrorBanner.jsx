export function ErrorBanner({ message, onRetry }) {
  if (!message) return null
  return (
    <div
      className="error-banner"
      role="alert"
      style={{
        padding: '12px 16px',
        marginBottom: 16,
        borderRadius: 8,
        background: '#fef2f2',
        border: '1px solid #fecaca',
        color: '#991b1b',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        flexWrap: 'wrap',
      }}
    >
      <span>{message}</span>
      {onRetry ? (
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  )
}
