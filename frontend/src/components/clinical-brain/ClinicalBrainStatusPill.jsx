import { GOAL_STATUS, STRATEGY_STATUS } from '../../lib/clinicalBrainStatus.js'

const TONE_CLASS = {
  active: 'cb-pill--active',
  pending: 'cb-pill--pending',
  warning: 'cb-pill--warning',
  success: 'cb-pill--success',
  muted: 'cb-pill--muted',
  progress: 'cb-pill--progress',
}

export function ClinicalBrainStatusPill({ status, kind = 'goal' }) {
  const map = kind === 'strategy' ? STRATEGY_STATUS : GOAL_STATUS
  const cfg = typeof status === 'string' ? map[status] : status
  if (!cfg) return null
  return (
    <span className={`cb-pill ${TONE_CLASS[cfg.tone] || 'cb-pill--muted'}`}>
      {cfg.label}
    </span>
  )
}
