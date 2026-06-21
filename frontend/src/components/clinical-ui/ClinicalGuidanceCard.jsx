import { ClinicalActionButton } from './ClinicalActionButton.jsx'

/**
 * Soft clinical guidance panel — not a dark AI chatbot block.
 * variant: 'guidance' (soft yellow) | 'success' (soft green) | 'neutral'
 */
export function ClinicalGuidanceCard({
  eyebrow = 'Clinical guidance',
  title,
  body,
  actionLabel,
  onAction,
  variant = 'guidance',
}) {
  return (
    <section className={`clinical-guidance-card clinical-guidance-card--${variant}`} aria-label={eyebrow}>
      <p className="clinical-guidance-card__eyebrow">{eyebrow}</p>
      {title ? <h3 className="clinical-guidance-card__title">{title}</h3> : null}
      {body ? <p className="clinical-guidance-card__body">{body}</p> : null}
      {actionLabel && onAction ? (
        <ClinicalActionButton variant="secondary" className="clinical-guidance-card__cta" onClick={onAction}>
          {actionLabel}
        </ClinicalActionButton>
      ) : null}
    </section>
  )
}
