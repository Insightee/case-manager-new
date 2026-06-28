import '../../styles/clinical-components.css'

/** Inner content wrapper for clinical/report pages — works inside existing app shell. */
export function ClinicalPageSurface({ children, className = '' }) {
  return (
    <div className={`clinical-page-surface ${className}`.trim()}>
      {children}
    </div>
  )
}
