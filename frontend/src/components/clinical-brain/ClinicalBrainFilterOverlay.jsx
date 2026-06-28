import { useState } from 'react'
import {
  AGE_GROUP_OPTIONS,
  DOMAIN_OPTIONS,
  EMPTY_FILTERS,
  ENVIRONMENT_OPTIONS,
  SERVICE_TYPE_OPTIONS,
  SUPPORT_LEVEL_OPTIONS,
  SUPPORT_NEED_OPTIONS,
} from '../../lib/clinicalBrainFilters.js'

const EVIDENCE_OPTIONS = [
  { id: 'new', label: 'New' },
  { id: 'emerging', label: 'Emerging' },
  { id: 'commonly_used', label: 'Commonly used' },
]

function FilterSection({ label, children }) {
  return (
    <div className="cb-filter-section">
      <p className="cb-filter-section__label">{label}</p>
      {children}
    </div>
  )
}

function ChipRow({ options, value, onChange }) {
  return (
    <div className="cb-filter-chips">
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          className={`cb-filter-chip${value === opt.id ? ' is-active' : ''}`}
          onClick={() => onChange(value === opt.id ? '' : opt.id)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export function ClinicalBrainFilterOverlay({
  open,
  onClose,
  filters: controlled,
  onChange,
  onApply,
  showSupportLevel = true,
  showEvidence = false,
  showStatus = false,
  statusOptions = [],
}) {
  const [draft, setDraft] = useState(controlled || EMPTY_FILTERS)

  if (!open) return null

  function patch(p) {
    setDraft((prev) => ({ ...prev, ...p }))
  }

  function apply() {
    onChange?.(draft)
    onApply?.(draft)
    onClose?.()
  }

  function clearAll() {
    const cleared = { ...EMPTY_FILTERS }
    setDraft(cleared)
    onChange?.(cleared)
  }

  return (
    <div className="cb-filter-overlay" role="dialog" aria-modal="true" aria-label="Filters">
      <button type="button" className="cb-filter-overlay__backdrop" aria-label="Close filters" onClick={onClose} />
      <div className="cb-filter-sheet">
        <header className="cb-filter-sheet__head">
          <h2 className="cb-filter-sheet__title">Filters</h2>
          <button type="button" className="cb-filter-sheet__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="cb-filter-sheet__body">
          <FilterSection label="Domain">
            <ChipRow options={DOMAIN_OPTIONS} value={draft.domain} onChange={(v) => patch({ domain: v })} />
          </FilterSection>
          <FilterSection label="Support need / issue">
            <ChipRow options={SUPPORT_NEED_OPTIONS} value={draft.supportNeed} onChange={(v) => patch({ supportNeed: v })} />
          </FilterSection>
          <FilterSection label="Environment">
            <ChipRow options={ENVIRONMENT_OPTIONS} value={draft.environment} onChange={(v) => patch({ environment: v })} />
          </FilterSection>
          <FilterSection label="Service type">
            <ChipRow options={SERVICE_TYPE_OPTIONS} value={draft.serviceType} onChange={(v) => patch({ serviceType: v })} />
          </FilterSection>
          <FilterSection label="Age group">
            <ChipRow options={AGE_GROUP_OPTIONS} value={draft.ageGroup} onChange={(v) => patch({ ageGroup: v })} />
          </FilterSection>
          {showSupportLevel ? (
            <FilterSection label="Support level">
              <ChipRow options={SUPPORT_LEVEL_OPTIONS} value={draft.supportLevel} onChange={(v) => patch({ supportLevel: v })} />
            </FilterSection>
          ) : null}
          {showEvidence ? (
            <FilterSection label="Evidence">
              <ChipRow options={EVIDENCE_OPTIONS} value={draft.evidenceStrength} onChange={(v) => patch({ evidenceStrength: v })} />
            </FilterSection>
          ) : null}
          {showStatus && statusOptions.length ? (
            <FilterSection label="Status">
              <ChipRow options={statusOptions} value={draft.status} onChange={(v) => patch({ status: v })} />
            </FilterSection>
          ) : null}
        </div>
        <footer className="cb-filter-sheet__foot">
          <button type="button" className="cb-btn cb-btn--ghost" onClick={clearAll}>
            Clear all
          </button>
          <button type="button" className="cb-btn cb-btn--primary" onClick={apply}>
            Apply filters
          </button>
        </footer>
      </div>
    </div>
  )
}
