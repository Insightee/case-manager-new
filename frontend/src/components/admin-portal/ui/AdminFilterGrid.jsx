/**
 * Standard admin filter bar layout (matches Report management & CM meetings).
 */
export function AdminFilterGrid({ children, className = '', ariaLabel = 'Filters' }) {
  return (
    <div
      className={`admin-meetings-filters admin-filter-grid ${className}`.trim()}
      role="group"
      aria-label={ariaLabel}
    >
      {children}
    </div>
  )
}
