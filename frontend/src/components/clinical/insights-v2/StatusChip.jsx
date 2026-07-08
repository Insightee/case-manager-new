import { statusTone } from '../../../lib/caseInsightsCompose.js'

const TONE_ICON = {
  positive: 'check_circle',
  progress: 'trending_up',
  attention: 'warning',
  muted: 'radio_button_unchecked',
}

export function StatusChip({ status, className = '' }) {
  if (!status) return null
  const tone = statusTone(status)
  return (
    <span className={`ci-chip ci-chip--${tone} ${className}`.trim()}>
      <span className="material-symbols-outlined ci-chip__icon" aria-hidden="true">
        {TONE_ICON[tone]}
      </span>
      {status}
    </span>
  )
}
