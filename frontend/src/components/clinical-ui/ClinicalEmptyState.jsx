import { ClinicalActionButton } from './ClinicalActionButton.jsx'

export function ClinicalEmptyState({
  icon,
  title,
  body,
  actionLabel,
  onAction,
  actionHref,
  variant = 'default',
}) {
  return (
    <div className={`clinical-empty-state${variant === 'upload' ? ' clinical-empty-state--upload' : ''}`}>
      {icon ? <span className="clinical-empty-state__icon" aria-hidden="true">{icon}</span> : null}
      {title ? <p className="clinical-empty-state__title">{title}</p> : null}
      {body ? <p className="clinical-empty-state__body">{body}</p> : null}
      {actionLabel && (onAction || actionHref) ? (
        actionHref ? (
          <ClinicalActionButton as="a" href={actionHref} variant="primary">{actionLabel}</ClinicalActionButton>
        ) : (
          <ClinicalActionButton variant="primary" onClick={onAction}>{actionLabel}</ClinicalActionButton>
        )
      ) : null}
    </div>
  )
}
