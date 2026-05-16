export function ClientPortalLayout({ title, subtitle, actionLabel, onAction, children }) {
  return (
    <>
      <header className="topbar">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <div className="topbar-actions">
          <input placeholder="Search case ID, child..." />
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
