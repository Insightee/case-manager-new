export function ClinicalCard({ children, className = '', title, subtitle, actions, headerActions, as: Tag = 'div', ...props }) {
  const hasStructure = title || subtitle || actions || headerActions
  if (!hasStructure) {
    return (
      <Tag className={`clinical-card cp-card ${className}`.trim()} {...props}>
        {children}
      </Tag>
    )
  }
  return (
    <Tag className={`clinical-card cp-card ${className}`.trim()} {...props}>
      {(title || subtitle || headerActions) ? (
        <div className="clinical-card__header">
          <div>
            {title ? <h3 className="clinical-card__title">{title}</h3> : null}
            {subtitle ? <p className="clinical-card__subtitle">{subtitle}</p> : null}
          </div>
          {headerActions ? (
            <div className="clinical-card__header-actions">{headerActions}</div>
          ) : null}
        </div>
      ) : null}
      {children ? <div className="clinical-card__body">{children}</div> : null}
      {actions ? <div className="clinical-card__actions">{actions}</div> : null}
    </Tag>
  )
}
