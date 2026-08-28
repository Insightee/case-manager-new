import { useEffect, useId, useMemo, useRef, useState } from 'react'
import './admin-multiselect.css'

/**
 * Checkbox multi-select dropdown matching admin filter styling.
 */
export function MultiSelect({
  label,
  options = [],
  values = [],
  onChange,
  id,
  placeholder = 'All',
  className = '',
  disabled = false,
  ariaLabel,
}) {
  const reactId = useId()
  const fieldId = id || `multiselect-${label?.replace(/\s+/g, '-').toLowerCase() || reactId}`
  const rootRef = useRef(null)
  const [open, setOpen] = useState(false)

  const selectedSet = useMemo(() => new Set(values.map(String)), [values])
  const selectedOptions = useMemo(
    () => options.filter((opt) => selectedSet.has(String(opt.value))),
    [options, selectedSet],
  )

  useEffect(() => {
    if (!open) return undefined
    function handlePointerDown(event) {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false)
      }
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  function toggleValue(value) {
    const next = String(value)
    const current = values.map(String)
    if (current.includes(next)) {
      onChange?.(current.filter((v) => v !== next))
      return
    }
    onChange?.([...current, next])
  }

  const summary = (() => {
    if (!selectedOptions.length) {
      return <span className="admin-multiselect__placeholder">{placeholder}</span>
    }
    if (selectedOptions.length === 1) {
      return <span className="admin-multiselect__chip">{selectedOptions[0].label}</span>
    }
    if (selectedOptions.length <= 2) {
      return selectedOptions.map((opt) => (
        <span key={String(opt.value)} className="admin-multiselect__chip">
          {opt.label}
        </span>
      ))
    }
    return <span className="admin-multiselect__count">{selectedOptions.length} selected</span>
  })()

  return (
    <div className={`admin-filter-field ${className}`.trim()} ref={rootRef}>
      {label ? (
        <span className="admin-filter-field__label" id={`${fieldId}-label`}>
          {label}
        </span>
      ) : null}
      <div className="admin-multiselect admin-filter-select">
        <button
          type="button"
          id={fieldId}
          className={`admin-multiselect__trigger${open ? ' is-open' : ''}`}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-labelledby={label ? `${fieldId}-label` : undefined}
          aria-label={ariaLabel || label || placeholder}
          disabled={disabled}
          onClick={() => setOpen((prev) => !prev)}
        >
          <span className="admin-multiselect__summary">{summary}</span>
        </button>
        <span className="admin-multiselect__chevron" aria-hidden>
          ▾
        </span>
        {open ? (
          <ul className="admin-multiselect__menu" role="listbox" aria-multiselectable="true" aria-labelledby={label ? `${fieldId}-label` : undefined}>
            {options.length === 0 ? (
              <li>
                <p className="admin-multiselect__empty">No people in this category yet.</p>
              </li>
            ) : (
              options.map((opt) => {
                const value = String(opt.value)
                const checked = selectedSet.has(value)
                return (
                  <li key={value} role="option" aria-selected={checked}>
                    <button
                      type="button"
                      className={`admin-multiselect__option${checked ? ' is-selected' : ''}`}
                      onClick={() => toggleValue(value)}
                    >
                      <input
                        type="checkbox"
                        className="admin-multiselect__checkbox"
                        checked={checked}
                        readOnly
                        tabIndex={-1}
                        aria-hidden
                      />
                      <span>{opt.label}</span>
                    </button>
                  </li>
                )
              })
            )}
          </ul>
        ) : null}
      </div>
    </div>
  )
}
