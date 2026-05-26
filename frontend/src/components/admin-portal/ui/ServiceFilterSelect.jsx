import { useClinicalProductModules } from '../../../hooks/useClinicalProductModules.js'

export function ServiceFilterSelect({
  value,
  onChange,
  className = 'admin-select',
  style,
  id = 'service-filter',
  extraOptions = [],
}) {
  const { options, loading } = useClinicalProductModules()

  return (
    <select
      id={id}
      className={className}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Service"
      disabled={loading && options.length <= 1}
      style={{ width: 'auto', minWidth: 160, ...style }}
    >
      {options.map((o) => (
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
