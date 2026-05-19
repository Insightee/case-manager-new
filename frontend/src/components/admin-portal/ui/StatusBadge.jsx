import { formatStatus, statusTone } from './adminUtils.js'

export function StatusBadge({ status, className = '' }) {
  const tone = statusTone(status)
  return (
    <span className={`admin-badge admin-badge--${tone} ${className}`.trim()}>
      {formatStatus(status)}
    </span>
  )
}
