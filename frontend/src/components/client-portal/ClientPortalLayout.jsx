import '../cases/my-cases.css'
import './client-portal-layout.css'
import './client-portal-mobile.css'
import './parent-portal-filters.css'

export function ClientPortalLayout({
  title,
  subtitle,
  actionLabel,
  onAction,
  hideSearch = true,
  children,
}) {
  return (
    <>
      <header className="ic-page-head client-portal-page-head">
        <div className="ic-page-head__text">
          <h1 className="ic-page-head__title">{title}</h1>
          {subtitle ? <p className="ic-page-head__sub">{subtitle}</p> : null}
        </div>
        {actionLabel || !hideSearch ? (
          <div className="ic-page-head__actions">
            {!hideSearch ? (
              <input
                className="ic-search"
                placeholder="Search case ID, child…"
                aria-label="Search cases"
              />
            ) : null}
            {actionLabel ? (
              <button type="button" className="ic-btn-cta" onClick={onAction}>
                {actionLabel}
              </button>
            ) : null}
          </div>
        ) : null}
      </header>
      {children}
    </>
  )
}
