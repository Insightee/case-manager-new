import { useEffect, useMemo, useState } from 'react'

const STAGE_OPTIONS = [
  { value: 'all', label: 'All stages' },
  { value: 'attention', label: 'Needs attention' },
  { value: 'log_due', label: 'Log due' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'closed', label: 'Closed' },
]

const DUE_OPTIONS = [
  { value: 'all', label: 'All deadlines' },
  { value: 'yes', label: 'Due soon' },
]

const SORT_OPTIONS = [
  { value: 'urgency', label: 'Sort by urgency' },
  { value: 'child', label: 'Sort by child' },
  { value: 'case_id', label: 'Sort by case ID' },
]

const MQ = '(max-width: 900px)'

function useCollapsibleFilters() {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(MQ).matches : false,
  )
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia(MQ)
    const onChange = () => {
      setIsMobile(mq.matches)
      if (!mq.matches) setOpen(false)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return { isMobile, open, setOpen, panelOpen: isMobile ? open : true }
}

function FilterFields({
  stage,
  onStageChange,
  service,
  onServiceChange,
  serviceOptions,
  dueSoon,
  onDueSoonChange,
  sort,
  onSortChange,
  hasActiveFilters,
  onClearFilters,
  stacked = false,
}) {
  return (
    <div className={`ic-filter-bar__filters${stacked ? ' ic-filter-bar__filters--stacked' : ''}`}>
      <label className="ic-filter-field">
        <span className="sr-only">Stage</span>
        <select
          className="ic-filter-select"
          value={stage}
          onChange={(e) => onStageChange(e.target.value)}
          aria-label="Filter by stage"
        >
          {STAGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label className="ic-filter-field">
        <span className="sr-only">Service</span>
        <select
          className="ic-filter-select"
          value={service}
          onChange={(e) => onServiceChange(e.target.value)}
          aria-label="Filter by service"
        >
          <option value="all">All services</option>
          {serviceOptions.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <label className="ic-filter-field">
        <span className="sr-only">Due soon</span>
        <select
          className="ic-filter-select"
          value={dueSoon}
          onChange={(e) => onDueSoonChange(e.target.value)}
          aria-label="Filter by deadline"
        >
          {DUE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.value === 'all' ? 'Due soon' : o.label}
            </option>
          ))}
        </select>
      </label>

      <label className="ic-filter-field">
        <span className="sr-only">Sort</span>
        <select
          className="ic-filter-select"
          value={sort}
          onChange={(e) => onSortChange(e.target.value)}
          aria-label="Sort cases"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      {hasActiveFilters ? (
        <button type="button" className="ic-filter-clear" onClick={onClearFilters}>
          Clear
        </button>
      ) : null}
    </div>
  )
}

export function FilterBar({
  view,
  onViewChange,
  stage,
  onStageChange,
  service,
  onServiceChange,
  serviceOptions = [],
  dueSoon,
  onDueSoonChange,
  sort,
  onSortChange,
  hasActiveFilters,
  onClearFilters,
}) {
  const { isMobile, open, setOpen, panelOpen } = useCollapsibleFilters()

  const activeCount = useMemo(() => {
    let n = 0
    if (stage !== 'all') n += 1
    if (service !== 'all') n += 1
    if (dueSoon !== 'all') n += 1
    if (sort !== 'urgency') n += 1
    return n
  }, [stage, service, dueSoon, sort])

  const fieldProps = {
    stage,
    onStageChange,
    service,
    onServiceChange,
    serviceOptions,
    dueSoon,
    onDueSoonChange,
    sort,
    onSortChange,
    hasActiveFilters,
    onClearFilters,
  }

  return (
    <div className="ic-filter-bar ic-filter-bar--collapsible">
      <div className="ic-filter-bar__toolbar">
        {isMobile ? (
          <button
            type="button"
            className="ic-filter-btn"
            aria-expanded={open}
            aria-controls="ic-filter-panel"
            onClick={() => setOpen((v) => !v)}
          >
            Filters
            {activeCount > 0 ? <span className="ic-filter-btn__badge">{activeCount}</span> : null}
          </button>
        ) : (
          <FilterFields {...fieldProps} />
        )}

        <div className="ic-filter-bar__views">
          <div className="ic-segment" role="group" aria-label="Layout">
            <button
              type="button"
              className={view === 'grid' ? 'active' : ''}
              onClick={() => onViewChange('grid')}
            >
              Grid
            </button>
            <button
              type="button"
              className={view === 'table' ? 'active' : ''}
              onClick={() => onViewChange('table')}
            >
              Table
            </button>
          </div>
        </div>
      </div>

      {isMobile && panelOpen ? (
        <div id="ic-filter-panel" className="ic-filter-bar__panel">
          <FilterFields {...fieldProps} stacked />
        </div>
      ) : null}
    </div>
  )
}
