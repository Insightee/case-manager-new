function FilterIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />
    </svg>
  )
}

export function CasesPageHeader({ search = '', onSearchChange }) {
  return (
    <header className="ic-page-head">
      <div className="ic-page-head__text">
        <h1 className="ic-page-head__title">My Cases</h1>
        <p className="ic-page-head__sub">Client files — sessions, reports, bookings, and deadlines in one place.</p>
      </div>
      <div className="ic-page-head__actions">
        <input
          type="search"
          className="ic-search"
          placeholder="Search child, case ID..."
          aria-label="Search cases"
          value={search}
          onChange={(e) => onSearchChange?.(e.target.value)}
        />
        <button type="button" className="ic-btn-icon" aria-label="Filters" disabled title="Filters coming soon">
          <FilterIcon />
        </button>
      </div>
    </header>
  )
}
