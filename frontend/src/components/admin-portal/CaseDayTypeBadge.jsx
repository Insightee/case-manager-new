import { dayTypeBadgeClass, dayTypeLabel } from '../../lib/dayTypeLabels.js'

export function CaseDayTypeBadge({ dayType, className = '' }) {
  const label = dayTypeLabel(dayType)
  if (!label) return null
  return (
    <span className={`${dayTypeBadgeClass(dayType)} ${className}`.trim()} title="School day coverage">
      {label}
    </span>
  )
}
