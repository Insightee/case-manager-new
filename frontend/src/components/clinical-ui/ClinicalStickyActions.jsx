export function ClinicalStickyActions({ children, className = '' }) {
  return (
    <div className={`clinical-sticky-actions cp-builder-sticky-actions ${className}`.trim()}>
      {children}
    </div>
  )
}
