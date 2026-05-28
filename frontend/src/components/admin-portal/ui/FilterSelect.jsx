/**
 * Accessible styled select for admin filter bars (touch-friendly, not plain grey native chrome).
 */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  id,
  className = '',
  disabled = false,
  ariaLabel,
}) {
  const selectId = id || `filter-${label?.replace(/\s+/g, '-').toLowerCase() || 'field'}`
  return (
    <label className={`admin-filter-field ${className}`.trim()} htmlFor={selectId}>
      {label ? <span className="admin-filter-field__label">{label}</span> : null}
      <span className="admin-filter-select">
        <select
          id={selectId}
          className="admin-filter-select__input"
          value={value}
          onChange={onChange}
          disabled={disabled}
          aria-label={ariaLabel || label || undefined}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <span className="admin-filter-select__chevron" aria-hidden>
          ▾
        </span>
      </span>
    </label>
  )
}

export function FilterDateRange({ label, from, to, onFromChange, onToChange, className = '' }) {
  return (
    <div className={`admin-filter-field admin-filter-field--range ${className}`.trim()}>
      {label ? <span className="admin-filter-field__label">{label}</span> : null}
      <div className="admin-filter-date-range">
        <input
          type="date"
          className="admin-filter-select__input admin-filter-date-range__input"
          value={from}
          onChange={onFromChange}
          aria-label={`${label || 'Opened'} from`}
        />
        <span className="admin-filter-date-range__sep">to</span>
        <input
          type="date"
          className="admin-filter-select__input admin-filter-date-range__input"
          value={to}
          onChange={onToChange}
          aria-label={`${label || 'Opened'} to`}
        />
      </div>
    </div>
  )
}
