import { useRouteError, Link } from 'react-router-dom'

export function PortalRouteError() {
  const error = useRouteError()
  const message =
    error instanceof Error
      ? error.message
      : typeof error === 'string'
        ? error
        : 'Something went wrong loading this page.'

  return (
    <div
      role="alert"
      style={{
        margin: '24px 0',
        padding: '16px 18px',
        borderRadius: 12,
        border: '1px solid #fecaca',
        background: '#fef2f2',
        color: '#991b1b',
      }}
    >
      <h2 style={{ margin: '0 0 8px', fontSize: '1.05rem', fontWeight: 700 }}>Page could not load</h2>
      <p style={{ margin: '0 0 12px', fontSize: '0.9rem', lineHeight: 1.45 }}>{message}</p>
      <Link to="/parent" style={{ fontWeight: 600, color: '#4338ca' }}>
        Back to dashboard
      </Link>
    </div>
  )
}
