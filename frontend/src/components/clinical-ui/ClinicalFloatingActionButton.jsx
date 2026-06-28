/**
 * Fixed bottom-right circular FAB.
 * Only rendered if onClick is provided.
 */
export function ClinicalFloatingActionButton({ label, onClick, icon = '+' }) {
  if (!onClick) return null
  return (
    <button
      type="button"
      className="clinical-fab"
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      {icon}
    </button>
  )
}
