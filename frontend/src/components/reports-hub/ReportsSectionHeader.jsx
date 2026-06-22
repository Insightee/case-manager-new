/** Shared Forest Light header for reports surfaces. */
export function ReportsSectionHeader({ title, subtitle, action, className = '' }) {
  return (
    <header className={`reports-hub-header${className ? ` ${className}` : ''}`}>
      <div className="reports-hub-header__copy">
        <h1 className="reports-hub-header__title">{title}</h1>
        {subtitle ? <p className="reports-hub-header__subtitle">{subtitle}</p> : null}
      </div>
      {action ? <div className="reports-hub-header__action">{action}</div> : null}
    </header>
  )
}
