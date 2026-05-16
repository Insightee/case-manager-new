const filters = ['Stage', 'Service', 'Due Soon', 'Sort by Urgency']

function Chevron() {
  return <span className="ic-chev" aria-hidden />
}

export function FilterBar({ view, onViewChange }) {
  return (
    <div className="ic-filter-bar">
      <div className="ic-filter-bar__filters">
        {filters.map((label) => (
          <button key={label} type="button" className="ic-filter-btn">
            {label}
            <Chevron />
          </button>
        ))}
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
        <div className="ic-icon-group" role="group" aria-label="Alternate views">
          <button type="button" className="ic-icon-btn" title="List">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
            </svg>
          </button>
          <button type="button" className="ic-icon-btn" title="Calendar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2" />
              <path d="M16 2v4M8 2v4M3 10h18" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
