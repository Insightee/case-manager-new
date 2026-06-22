import { useEffect, useRef, useState } from 'react'
import { CORE_DOMAINS, CORE_ENVIRONMENTS, coreDomainLabel, coreEnvironmentLabel } from '../../lib/coreClinicalTaxonomy.js'

function chipLabel(options, id) {
  const row = options.find((o) => o.id === id)
  return row?.short || row?.label || id
}

function MultiSelectDropdown({ label, options, value = [], onChange, disabled }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const selected = Array.isArray(value) ? value : []

  useEffect(() => {
    if (!open) return undefined
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  function toggle(id) {
    if (disabled) return
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }

  const summary =
    selected.length === 0
      ? `Select ${label.toLowerCase()}…`
      : selected.map((id) => chipLabel(options, id)).join(', ')

  return (
    <div className="sl-taxonomy-dropdown" ref={ref}>
      <p className="sl-taxonomy-dropdown__label">{label}</p>
      <button
        type="button"
        className="sl-taxonomy-dropdown__trigger"
        disabled={disabled}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="sl-taxonomy-dropdown__summary">{summary}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {open ? (
        <div className="sl-taxonomy-dropdown__menu" role="listbox" aria-label={label}>
          {options.map((opt) => (
            <label key={opt.id} className="sl-taxonomy-dropdown__option">
              <input
                type="checkbox"
                checked={selected.includes(opt.id)}
                disabled={disabled}
                onChange={() => toggle(opt.id)}
              />
              <span>{opt.short || opt.label}</span>
            </label>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function CompactChips({ options, value = [], onChange, disabled }) {
  const selected = Array.isArray(value) ? value : []

  function toggle(id) {
    if (disabled) return
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }

  return (
    <div className="sl-chip-picker__row sl-chip-picker__row--compact" role="group">
      {options.map((opt) => {
        const active = selected.includes(opt.id)
        return (
          <button
            key={opt.id}
            type="button"
            disabled={disabled}
            className={`sl-chip-picker__chip sl-chip-picker__chip--compact${active ? ' is-active' : ''}`}
            aria-pressed={active}
            onClick={() => toggle(opt.id)}
          >
            {opt.short || opt.label}
          </button>
        )
      })}
    </div>
  )
}

export function ClinicalTaxonomyPicker({
  domains = [],
  environments = [],
  onDomainsChange,
  onEnvironmentsChange,
  disabled = false,
}) {
  return (
    <div className="sl-taxonomy-split">
      <div className="sl-taxonomy-split__col sl-taxonomy-split__col--desktop">
        <p className="sl-taxonomy-split__heading">Domains</p>
        <CompactChips options={CORE_DOMAINS} value={domains} onChange={onDomainsChange} disabled={disabled} />
      </div>
      <div className="sl-taxonomy-split__col sl-taxonomy-split__col--desktop">
        <p className="sl-taxonomy-split__heading">Environments</p>
        <CompactChips
          options={CORE_ENVIRONMENTS}
          value={environments}
          onChange={onEnvironmentsChange}
          disabled={disabled}
        />
      </div>
      <div className="sl-taxonomy-split__mobile">
        <MultiSelectDropdown
          label="Domains"
          options={CORE_DOMAINS}
          value={domains}
          onChange={onDomainsChange}
          disabled={disabled}
        />
        <MultiSelectDropdown
          label="Environments"
          options={CORE_ENVIRONMENTS}
          value={environments}
          onChange={onEnvironmentsChange}
          disabled={disabled}
        />
      </div>
    </div>
  )
}

export function TaxonomyTicker({ domains = [], environments = [] }) {
  if (!domains.length && !environments.length) return null
  return (
    <div className="sl-taxonomy-tickers">
      {domains.map((id) => (
        <span key={`d-${id}`} className="sl-taxonomy-ticker sl-taxonomy-ticker--domain">
          {coreDomainLabel(id, { short: true })}
        </span>
      ))}
      {environments.map((id) => (
        <span key={`e-${id}`} className="sl-taxonomy-ticker sl-taxonomy-ticker--env">
          {coreEnvironmentLabel(id, { short: true })}
        </span>
      ))}
    </div>
  )
}
