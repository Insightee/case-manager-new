/** Shared underline tab bar for admin/HR portal pages. */
export function PortalTabBar({ tabs, activeId, onChange, ariaLabel = 'Sections', className = '' }) {
  return (
    <div className={`portal-tabs ${className}`.trim()} role="tablist" aria-label={ariaLabel}>
      {tabs.map(({ id, label, badge }) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={activeId === id}
          className={`portal-tabs__tab ${activeId === id ? 'is-active' : ''}`}
          onClick={() => onChange(id)}
        >
          {label}
          {badge != null && badge !== '' ? ` (${badge})` : ''}
        </button>
      ))}
    </div>
  )
}
