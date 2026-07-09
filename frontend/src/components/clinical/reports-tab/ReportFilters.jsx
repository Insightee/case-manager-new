import { useMemo, useState } from 'react'

const TYPE_OPTIONS = [
  { value: 'all', label: 'All types' },
  { value: 'observation_report', label: 'Observation' },
  { value: 'monthly_report', label: 'Monthly' },
  { value: 'iep', label: 'IEP' },
  { value: 'progress_report', label: 'Progress' },
  { value: 'cm_meeting_note', label: 'CM Meeting' },
]

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'pending_cm_approval', label: 'Pending CM' },
  { value: 'needs_changes', label: 'Needs changes' },
  { value: 'overdue', label: 'Overdue' },
]

function SearchField({ filters, onChange }) {
  return (
    <div className="crt-filters__search">
      <span className="material-symbols-outlined" aria-hidden="true">search</span>
      <input
        type="search"
        placeholder="Search reports…"
        value={filters.search}
        onChange={(e) => onChange({ ...filters, search: e.target.value })}
        aria-label="Search reports"
      />
    </div>
  )
}

function SelectFields({ filters, onChange, monthOptions, yearOptions }) {
  return (
    <div className="crt-filters__selects">
      <label className="crt-filters__field">
        <span className="crt-filters__field-label">Month</span>
        <select
          value={filters.month}
          onChange={(e) => onChange({ ...filters, month: e.target.value })}
          aria-label="Filter by month"
        >
          <option value="all">All months</option>
          {monthOptions.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
      <label className="crt-filters__field">
        <span className="crt-filters__field-label">Year</span>
        <select
          value={filters.year}
          onChange={(e) => onChange({ ...filters, year: e.target.value })}
          aria-label="Filter by year"
        >
          <option value="all">All years</option>
          {yearOptions.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
      <label className="crt-filters__field">
        <span className="crt-filters__field-label">Type</span>
        <select
          value={filters.type}
          onChange={(e) => onChange({ ...filters, type: e.target.value })}
          aria-label="Filter by report type"
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
      <label className="crt-filters__field">
        <span className="crt-filters__field-label">Status</span>
        <select
          value={filters.status}
          onChange={(e) => onChange({ ...filters, status: e.target.value })}
          aria-label="Filter by status"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </label>
    </div>
  )
}

export function ReportFilters({
  filters,
  onChange,
  monthOptions = [],
  yearOptions = [],
}) {
  const [sheetOpen, setSheetOpen] = useState(false)

  const activeCount = useMemo(() => {
    let n = 0
    if (filters.month !== 'all') n += 1
    if (filters.year !== 'all') n += 1
    if (filters.type !== 'all') n += 1
    if (filters.status !== 'all') n += 1
    return n
  }, [filters])

  const clearAll = () =>
    onChange({ search: '', month: 'all', year: 'all', type: 'all', status: 'all' })

  return (
    <section className="crt-filters">
      <div className="crt-filters__desktop">
        <SearchField filters={filters} onChange={onChange} />
        <SelectFields
          filters={filters}
          onChange={onChange}
          monthOptions={monthOptions}
          yearOptions={yearOptions}
        />
        <button type="button" className="crt-filters__clear" onClick={clearAll}>
          Clear Filters
        </button>
      </div>

      <div className="crt-filters__mobile">
        <div className="crt-filters__mobile-bar">
          <SearchField filters={filters} onChange={onChange} />
          <button
            type="button"
            className="crt-filters__toggle"
            onClick={() => setSheetOpen(true)}
            aria-expanded={sheetOpen}
          >
            <span className="material-symbols-outlined" aria-hidden="true">tune</span>
            <span>Filters</span>
            {activeCount > 0 ? (
              <span className="crt-filters__badge" aria-label={`${activeCount} active`}>
                {activeCount}
              </span>
            ) : null}
          </button>
        </div>

        {sheetOpen ? (
          <>
            <button
              type="button"
              className="crt-filters__backdrop"
              aria-label="Dismiss filters"
              onClick={() => setSheetOpen(false)}
            />
            <div className="crt-filters__sheet" role="dialog" aria-modal="true" aria-label="Report filters">
              <div className="crt-filters__sheet-head">
                <strong>Filters</strong>
                <button type="button" onClick={() => setSheetOpen(false)} aria-label="Close filters">
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
              <SelectFields
                filters={filters}
                onChange={onChange}
                monthOptions={monthOptions}
                yearOptions={yearOptions}
              />
              <div className="crt-filters__sheet-actions">
                <button type="button" className="crt-filters__clear" onClick={clearAll}>
                  Clear all
                </button>
                <button
                  type="button"
                  className="crt-filters__apply"
                  onClick={() => setSheetOpen(false)}
                >
                  Done
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </section>
  )
}
