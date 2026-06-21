export function ClinicalGhostButton({ children, disabled = false, type = 'button', onClick, className = '' }) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`clinical-btn-ghost ${className}`.trim()}
    >
      {children}
    </button>
  )
}
