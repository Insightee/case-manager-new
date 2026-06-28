/**
 * Purple filled button. fullWidth adds 100% width.
 */
export function ClinicalPrimaryButton({ children, fullWidth = false, disabled = false, type = 'button', onClick, className = '' }) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`clinical-btn-primary${fullWidth ? ' clinical-btn-primary--full' : ''} ${className}`.trim()}
    >
      {children}
    </button>
  )
}
