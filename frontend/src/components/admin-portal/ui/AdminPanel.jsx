export function AdminPanel({ title, subtitle, actions, children, className = '', padded = true }) {
  return (
    <section className={`admin-panel ${className}`.trim()}>
      {title || actions ? (
        <header className="admin-panel__head">
          <div>
            {title ? <h3 className="admin-panel__title">{title}</h3> : null}
            {subtitle ? <p className="admin-panel__sub">{subtitle}</p> : null}
          </div>
          {actions ? <div className="admin-panel__actions">{actions}</div> : null}
        </header>
      ) : null}
      <div className={padded ? 'admin-panel__body' : 'admin-panel__body admin-panel__body--flush'}>
        {children}
      </div>
    </section>
  )
}
