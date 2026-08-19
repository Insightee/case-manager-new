const STATUS_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'under_review', label: 'Under Review' },
  { value: 'published', label: 'Published' },
  { value: 'attention', label: 'Needs Attention' },
]

const TYPE_OPTIONS = [
  { value: 'all', label: 'All Types' },
  { value: 'monthly', label: 'Monthly Report' },
  { value: 'progress', label: 'Progress Report' },
]

export function ReportsDashboardFilters({ draft, onDraftChange, onApply, caseOptions = [] }) {
  return (
    <div className="reports-dashboard-filters">
      <label className="reports-dashboard-filters__field">
        <span className="reports-dashboard-filters__label">Report Status</span>
        <select
          className="reports-dashboard-filters__select"
          value={draft.status}
          onChange={(e) => onDraftChange({ ...draft, status: e.target.value })}
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </label>
      <label className="reports-dashboard-filters__field">
        <span className="reports-dashboard-filters__label">Report Type</span>
        <select
          className="reports-dashboard-filters__select"
          value={draft.type}
          onChange={(e) => onDraftChange({ ...draft, type: e.target.value })}
        >
          {TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </label>
      <label className="reports-dashboard-filters__field">
        <span className="reports-dashboard-filters__label">Case</span>
        <select
          className="reports-dashboard-filters__select"
          value={draft.case}
          onChange={(e) => onDraftChange({ ...draft, case: e.target.value })}
        >
          <option value="all">All Cases</option>
          {caseOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </label>
      <button type="button" className="reports-dashboard-filters__apply" onClick={onApply}>
        Apply Filters
      </button>
    </div>
  )
}

export { STATUS_OPTIONS, TYPE_OPTIONS }
