/**
 * Mobile-first filter row for parent portal pages.
 * Labels stack above full-width controls; grid expands at tablet/desktop breakpoints.
 */
export function ParentFilterBar({
  children,
  actions,
  className = '',
  gridClass = 'parent-portal-filters__grid--tablet-2 parent-portal-filters__grid--desktop-3',
  ariaLabel = 'Filters',
  layout = 'stack',
}) {
  const rootClass = [
    'parent-portal-filters',
    layout === 'row' ? 'parent-portal-filters--row' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={rootClass} aria-label={ariaLabel}>
      <div className={`parent-portal-filters__grid ${gridClass}`}>{children}</div>
      {actions ? <div className="parent-portal-filters__actions">{actions}</div> : null}
    </div>
  )
}

export function ParentFilterField({ label, children, className = '' }) {
  return (
    <label className={`parent-portal-filters__field ${className}`.trim()}>
      <span className="parent-portal-filters__label">{label}</span>
      {children}
    </label>
  )
}

export function ParentFilterSelect(props) {
  return <select className="parent-portal-filters__control" {...props} />
}

export function ParentPortalTabs({ tabs, value, onChange, ariaLabel = 'Sections' }) {
  return (
    <nav className="parent-portal-tabs" aria-label={ariaLabel}>
      {tabs.map((t) => (
        <button
          key={t.id || 'all'}
          type="button"
          className={`parent-portal-tabs__tab ${value === t.id ? 'is-active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}
