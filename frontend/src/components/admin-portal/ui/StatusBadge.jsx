import { formatStatus, statusTone } from './adminUtils.js'

export function StatusBadge({ status, tone: toneProp, children, className = '' }) {
  const label = children ?? formatStatus(status)
  const tone = toneProp ?? statusTone(status)
  return (
    <span className={`admin-badge admin-badge--${tone} ${className}`.trim()}>
      {label}
    </span>
  )
}
