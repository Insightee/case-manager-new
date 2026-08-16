export function TransitionLogBadge({ log, className = '' }) {
  if (!log?.is_transition_log && !log?.transition_id) return null

  return (
    <span
      className={`admin-badge admin-badge--info sessions-dash__pill ${className}`.trim()}
      title="This log was submitted for a therapist handover day"
    >
      Transition log
    </span>
  )
}
