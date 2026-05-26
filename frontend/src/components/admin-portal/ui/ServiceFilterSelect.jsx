import { SERVICE_OPTIONS } from '../../../lib/serviceFilters.js'

export function ServiceFilterSelect({
  value,
  onChange,
  className = 'admin-select',
  style,
  id = 'service-filter',
  extraOptions = [],
}) {
  return (
    <select
      id={id}
      className={className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Service"
      style={{ width: 'auto', minWidth: 160, ...style }}
    >
      {SERVICE_OPTIONS.map((o) => (
        <option key={o.value || 'all'} value={o.value}>
          {o.label}
        </option>
      ))}
      {extraOptions.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}
