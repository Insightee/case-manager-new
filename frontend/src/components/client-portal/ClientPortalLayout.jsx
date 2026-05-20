export function ClientPortalLayout({ title, subtitle, actionLabel, onAction, hideSearch = true, children }) {
  return (
    <>
      <header className="topbar">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <div className="topbar-actions">
          {!hideSearch ? <input placeholder="Search case ID, child..." aria-label="Search cases" /> : null}
          {actionLabel ? (
            <button type="button" onClick={onAction}>
              {actionLabel}
            </button>
          ) : null}
        </div>
      </header>

      {children}
    </>
  )
}
