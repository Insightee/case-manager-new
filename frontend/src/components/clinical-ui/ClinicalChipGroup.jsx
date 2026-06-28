/** Reusable chip group — 44px touch targets, mobile-first */

export function ClinicalChipGroup({
  label,
  options = [],
  value,
  values,
  multi = false,
  required = false,
  readOnly = false,
  onChange,
  className = '',
}) {
  const selected = multi ? new Set(values || []) : value

  function isActive(id) {
    return multi ? selected.has(id) : selected === id
  }

  function toggle(id) {
    if (readOnly) return
    if (multi) {
      const next = new Set(selected)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      onChange?.([...next])
      return
    }
    onChange?.(isActive(id) ? null : id)
  }

  return (
    <div className={`clinical-chip-group ${className}`.trim()}>
      {label ? (
        <p className="clinical-chip-group__label">
          {label}
          {required ? <span className="clinical-chip-group__req"> · helpful to add</span> : null}
        </p>
      ) : null}
      <div className="clinical-chip-group__row" role={multi ? 'group' : 'radiogroup'} aria-label={label}>
        {options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            disabled={readOnly}
            className={`clinical-chip${isActive(opt.id) ? ' is-active' : ''}`}
            aria-pressed={isActive(opt.id)}
            onClick={() => toggle(opt.id)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/** Segmented control for strategy use status */
export function ClinicalSegmentControl({ label, options = [], value, readOnly = false, onChange }) {
  return (
    <div className="clinical-segment">
      {label ? <p className="clinical-chip-group__label">{label}</p> : null}
      <div className="clinical-segment__row" role="radiogroup" aria-label={label}>
        {options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            disabled={readOnly}
            className={`clinical-segment__btn${value === opt.id ? ' is-active' : ''}`}
            aria-pressed={value === opt.id}
            onClick={() => !readOnly && onChange?.(value === opt.id ? null : opt.id)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}
