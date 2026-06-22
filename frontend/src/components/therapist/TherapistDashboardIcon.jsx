/** Material Symbols icon tile for therapist dashboard actions. */
export function TherapistDashboardIcon({ name, tone = 'forest', className = '' }) {
  if (!name) return null
  return (
    <span
      className={`therapist-dash-icon therapist-dash-icon--${tone}${className ? ` ${className}` : ''}`}
      aria-hidden="true"
    >
      <span className="material-symbols-outlined">{name}</span>
    </span>
  )
}
