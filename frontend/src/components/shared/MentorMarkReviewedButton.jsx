/** One-way mentor mark-as-reviewed control for session logs. */
export function MentorMarkReviewedButton({ log, onMarked, disabled = false, className = '' }) {
  if (!log?.can_mark_mentor_reviewed) return null
  return (
    <button
      type="button"
      className={`admin-btn admin-btn--secondary admin-btn--sm ${className}`.trim()}
      disabled={disabled}
      onClick={() => onMarked?.(log.id)}
    >
      {disabled ? 'Marking…' : 'Mark as reviewed'}
    </button>
  )
}
