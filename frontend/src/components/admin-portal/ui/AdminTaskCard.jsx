export function AdminTaskCard({
  title,
  meta,
  badges,
  actions,
  children,
  highlight = false,
  className = '',
}) {
  return (
    <article
      className={`admin-task-card${highlight ? ' is-highlight' : ''}${className ? ` ${className}` : ''}`}
    >
      <div className="admin-task-card__head">
        <div>
          {title ? <h3 className="admin-task-card__title">{title}</h3> : null}
          {meta ? <p className="admin-task-card__meta">{meta}</p> : null}
        </div>
        {badges ? <div className="admin-task-card__badges">{badges}</div> : null}
      </div>
      {actions ? <div className="admin-task-card__actions">{actions}</div> : null}
      {children ? (
        <details className="admin-task-card__details">
          <summary>More details</summary>
          <div className="admin-task-card__body">{children}</div>
        </details>
      ) : null}
    </article>
  )
}
