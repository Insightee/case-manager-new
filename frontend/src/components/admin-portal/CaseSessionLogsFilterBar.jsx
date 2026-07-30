import {
  CASE_SESSION_LOG_STATUS_FILTERS,
  CASE_SESSION_LOG_VIEW_MODES,
} from '../../lib/caseSessionLogFilters.js'

export function CaseSessionLogsFilterBar({
  viewMode,
  selectedMonth,
  selectedDate,
  statusFilter,
  onViewModeChange,
  onSelectedMonthChange,
  onSelectedDateChange,
  onStatusFilterChange,
}) {
  return (
    <div className="case-sessions-logs-filters" aria-label="Filter session logs">
      <div className="case-sessions-logs-filters__grid">
        <label className="case-sessions-logs-filters__field">
          <span className="case-sessions-logs-filters__label">View</span>
          <span className="case-sessions-logs-filters__select-wrap">
            <select
              className="case-sessions-logs-filters__control"
              value={viewMode}
              onChange={(e) => onViewModeChange(e.target.value)}
              aria-label="Session logs view"
            >
              {CASE_SESSION_LOG_VIEW_MODES.map((mode) => (
                <option key={mode.value} value={mode.value}>
                  {mode.label}
                </option>
              ))}
            </select>
          </span>
        </label>

        {viewMode === 'day' ? (
          <label className="case-sessions-logs-filters__field">
            <span className="case-sessions-logs-filters__label">Date</span>
            <input
              type="date"
              className="case-sessions-logs-filters__control case-sessions-logs-filters__control--date"
              value={selectedDate}
              onChange={(e) => onSelectedDateChange(e.target.value)}
              aria-label="Session date"
            />
          </label>
        ) : null}

        {viewMode === 'month' ? (
          <label className="case-sessions-logs-filters__field">
            <span className="case-sessions-logs-filters__label">Month</span>
            <input
              type="month"
              className="case-sessions-logs-filters__control case-sessions-logs-filters__control--date"
              value={selectedMonth}
              onChange={(e) => onSelectedMonthChange(e.target.value)}
              aria-label="Session month"
            />
          </label>
        ) : null}

        <label className="case-sessions-logs-filters__field">
          <span className="case-sessions-logs-filters__label">Status</span>
          <span className="case-sessions-logs-filters__select-wrap">
            <select
              className="case-sessions-logs-filters__control"
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value)}
              aria-label="Session log status"
            >
              {CASE_SESSION_LOG_STATUS_FILTERS.map((f) => (
                <option key={f.value || 'all'} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </span>
        </label>
      </div>
    </div>
  )
}
