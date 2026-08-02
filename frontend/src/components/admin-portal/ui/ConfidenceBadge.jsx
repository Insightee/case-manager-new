import { confidenceTooltip, normalizeConfidence } from '../../../lib/financeConfidence.js'

const TONE = {
  RECONCILED: 'success',
  PARTIAL: 'info',
  ESTIMATED: 'warning',
  INCOMPLETE: 'neutral',
}

const LABEL = {
  RECONCILED: 'Reconciled',
  PARTIAL: 'Partial',
  ESTIMATED: 'Estimated',
  INCOMPLETE: 'Incomplete',
}

/**
 * Shared confidence badge — text label + tooltip, not colour-only.
 * Reusable outside finance (Forest Light / admin badge tones).
 */
export function ConfidenceBadge({
  confidence,
  reason,
  materialSourceMissing = false,
  className = '',
}) {
  const level = normalizeConfidence(confidence, { materialSourceMissing })
  const tone = TONE[level] || 'neutral'
  const label = LABEL[level] || level
  const tip = reason || confidenceTooltip(level)
  return (
    <span
      className={`admin-badge admin-badge--${tone} finance-confidence-badge ${className}`.trim()}
      title={tip}
      aria-label={`Data confidence: ${label}. ${tip}`}
    >
      {label}
    </span>
  )
}
