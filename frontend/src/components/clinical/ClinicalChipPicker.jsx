export function ClinicalChipPicker({ label, options, value = [], onChange, disabled = false, single = false }) {
  const selected = Array.isArray(value) ? value : value ? [value] : []

  function toggle(id) {
    if (disabled) return
    if (single) {
      onChange(selected[0] === id ? [] : [id])
      return
    }
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }

  return (
    <div className="sl-chip-picker">
      {label ? <p className="sl-v2-section-label">{label}</p> : null}
      <div className="sl-chip-picker__row" role="group" aria-label={label}>
        {options.map((opt) => {
          const active = selected.includes(opt.id)
          return (
            <button
              key={opt.id}
              type="button"
              disabled={disabled}
              className={`sl-chip-picker__chip${active ? ' is-active' : ''}`}
              aria-pressed={active}
              onClick={() => toggle(opt.id)}
            >
              {opt.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
