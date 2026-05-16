const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'submitted', label: 'Submitted' },
  { id: 'pending', label: 'Pending' },
  { id: 'approved', label: 'Approved' },
  { id: 'missing', label: 'Missing' },
]

export function FilterBar({ value, onChange }) {
  return (
    <div
      className="flex flex-wrap items-center gap-2"
      role="tablist"
      aria-label="Filter logs by status"
    >
      <span className="mr-1 text-xs font-medium uppercase tracking-wide text-slate-500">Status</span>
      {FILTERS.map((f) => (
        <button
          key={f.id}
          type="button"
          role="tab"
          aria-selected={value === f.id}
          onClick={() => onChange(f.id)}
          className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
            value === f.id
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white text-slate-600 ring-1 ring-[#E2E8F0] hover:bg-slate-50'
          }`}
        >
          {f.label}
        </button>
      ))}
    </div>
  )
}
