export function AdminPageHeader({ title, subtitle, eyebrow, actions, children }) {
  return (
    <header className="admin-page-header">
      <div className="admin-page-header__main">
        {eyebrow ? <p className="admin-page-header__eyebrow">{eyebrow}</p> : null}
        <h2 className="admin-page-header__title">{title}</h2>
        {subtitle ? <p className="admin-page-header__sub">{subtitle}</p> : null}
        {children}
      </div>
      {actions ? <div className="admin-page-header__actions">{actions}</div> : null}
    </header>
  )
}
