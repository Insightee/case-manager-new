export function transitionRoleLabel(role) {
  if (role === 'outgoing') return 'Outgoing therapist'
  if (role === 'incoming') return 'Incoming therapist'
  return ''
}

export function TransitionLogBadge({ log, className = '' }) {
  if (!log?.is_transition_log && !log?.transition_id) return null
  const role = transitionRoleLabel(log.transition_role)
  const day =
    log.transition_day_number && log.transition_day_count
      ? `Day ${log.transition_day_number} of ${log.transition_day_count}`
      : ''
  const detail = [role, day].filter(Boolean).join(' · ')

  return (
    <span
      className={`admin-badge admin-badge--info sessions-dash__pill ${className}`.trim()}
      title="This log was submitted for a therapist handover day"
    >
      Transition log{detail ? ` · ${detail}` : ''}
    </span>
  )
}
