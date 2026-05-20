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
  return (
    <div className="ic-filter-bar">
      <div className="ic-filter-bar__filters">
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
  )
}
