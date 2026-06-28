/**
 * Labelled progress bar.
 * pct: 0–100
 * variant: 'default' | 'green' | 'amber'
 */
export function ClinicalProgressBar({ label, pct = 0, variant = 'default', showPct = true }) {
  const clamped = Math.max(0, Math.min(100, pct))
  const fillCls = variant === 'green'
    ? 'clinical-progress-bar__fill--green'
    : variant === 'amber'
    ? 'clinical-progress-bar__fill--amber'
    : ''

  return (
    <div className="clinical-progress-bar">
      {(label || showPct) ? (
        <div className="clinical-progress-bar__header">
          {label ? <span className="clinical-progress-bar__label">{label}</span> : null}
          {showPct ? <span className="clinical-progress-bar__pct">{clamped}%</span> : null}
        </div>
      ) : null}
      <div className="clinical-progress-bar__track" role="progressbar" aria-valuenow={clamped} aria-valuemin={0} aria-valuemax={100}>
        <div className={`clinical-progress-bar__fill ${fillCls}`.trim()} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  )
}
