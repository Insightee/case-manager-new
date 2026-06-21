export function ClinicalSecondaryButton({ children, disabled = false, type = 'button', onClick, className = '' }) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`clinical-btn-secondary ${className}`.trim()}
    >
      {children}
    </button>
  )
}
