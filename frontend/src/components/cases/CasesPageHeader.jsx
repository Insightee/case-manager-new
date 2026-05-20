export function CasesPageHeader({ search = '', onSearchChange, resultCount, totalCount }) {
  const q = search.trim()
  const showCount = q && typeof resultCount === 'number' && typeof totalCount === 'number'

  return (
    <header className="ic-page-head">
      <div className="ic-page-head__text">
        <h1 className="ic-page-head__title">My Cases</h1>
        <p className="ic-page-head__sub">
          Client files — sessions, reports, bookings, and deadlines in one place.
          {showCount ? (
            <span className="ic-page-head__count">
              {' '}
              · {resultCount} of {totalCount} shown
            </span>
          ) : null}
        </p>
      </div>
      <div className="ic-page-head__actions">
        <input
          type="search"
          className="ic-search"
          placeholder="Search child, case ID, service..."
          aria-label="Search cases"
          value={search}
          onChange={(e) => onSearchChange?.(e.target.value)}
        />
      </div>
    </header>
  )
}
