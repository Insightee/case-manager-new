function FilterIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />
    </svg>
  )
}

/**
 * My Cases top area: title, subtitle, search, filter icon, CTA.
 */
export function CasesPageHeader() {
  return (
    <header className="ic-page-head">
      <div className="ic-page-head__text">
        <h1 className="ic-page-head__title">My Cases</h1>
        <p className="ic-page-head__sub">Track case stages, pending actions, and deadlines.</p>
      </div>
      <div className="ic-page-head__actions">
        <input
          type="search"
          className="ic-search"
          placeholder="Search child, case ID..."
          aria-label="Search cases"
        />
        <button type="button" className="ic-btn-icon" aria-label="Filters">
          <FilterIcon />
        </button>
        <button type="button" className="ic-btn-cta">
          + Add Note
        </button>
      </div>
    </header>
  )
}
