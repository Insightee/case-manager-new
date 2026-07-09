import { statusTone } from '../../../lib/caseReportsCompose.js'

const TONE_ICON = {
  positive: 'check_circle',
  progress: 'schedule',
  attention: 'warning',
  muted: 'radio_button_unchecked',
}

export function ReportStatusChip({ status, statusLabel, className = '' }) {
  const label = statusLabel || status
  if (!label) return null
  const tone = statusTone(status, statusLabel)
  return (
    <span className={`crt-chip crt-chip--${tone} ${className}`.trim()}>
      <span className="material-symbols-outlined crt-chip__icon" aria-hidden="true">
        {TONE_ICON[tone]}
      </span>
      {label}
    </span>
  )
}
