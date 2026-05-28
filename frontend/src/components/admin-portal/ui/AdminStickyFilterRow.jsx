/**
 * Sticky horizontal filter row for mobile — inline controls without a separate Filters drawer.
 */
export function AdminStickyFilterRow({ children, className = '', ariaLabel = 'Filters' }) {
  return (
    <div
      className={`admin-sticky-filter-row admin-mobile-only ${className}`.trim()}
      role="group"
      aria-label={ariaLabel}
    >
      <div className="admin-sticky-filter-row__scroll">{children}</div>
    </div>
  )
}
