import './route-loading.css'

export function RouteLoading({ label = 'Loading…' }) {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <span className="route-loading__spinner" aria-hidden />
      <span>{label}</span>
    </div>
  )
}
