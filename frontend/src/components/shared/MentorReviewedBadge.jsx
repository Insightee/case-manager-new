/** Badge when a mentor has marked a session log as reviewed. */
export function MentorReviewedBadge({ log, className = '' }) {
  if (!log?.mentor_reviewed && !log?.mentor_reviewed_at) return null
  const name = log.mentor_reviewed_by_name
  const label = name ? `Reviewed by mentor · ${name}` : 'Reviewed by mentor'
  return (
    <span
      className={`admin-badge admin-badge--info sessions-dash__pill ${className}`.trim()}
      title={label}
    >
      {label}
    </span>
  )
}
