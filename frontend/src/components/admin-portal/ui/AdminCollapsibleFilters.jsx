import { useEffect, useState } from 'react'

const MQ = '(max-width: 900px)'

function useIsAdminMobile() {
  const [mobile, setMobile] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(MQ).matches : false,
  )

  useEffect(() => {
    const mq = window.matchMedia(MQ)
    const onChange = () => setMobile(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  return mobile
}

/**
 * @param {object} props
 * @param {React.ReactNode} [props.quickSearch] - Always visible on mobile (e.g. search input)
 * @param {string[]} [props.activeChips] - Short labels for active filters
 * @param {number} [props.activeCount] - Badge on Filters button
 * @param {React.ReactNode} props.children - Full filter form (grid)
 */
export function AdminCollapsibleFilters({
  quickSearch,
  activeChips = [],
  activeCount,
  children,
  filtersOnly = false,
  mobileActions = null,
  open: controlledOpen,
  onOpenChange,
  defaultOpen = false,
  collapseOnDesktop = false,
}) {
  const isMobile = useIsAdminMobile()
  const [internalOpen, setInternalOpen] = useState(defaultOpen)
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen

  function setOpen(next) {
    const value = typeof next === 'function' ? next(open) : next
    if (onOpenChange) onOpenChange(value)
    else setInternalOpen(value)
  }

  useEffect(() => {
    if (!isMobile && controlledOpen === undefined) setInternalOpen(false)
  }, [isMobile, controlledOpen])

  const count = activeCount ?? activeChips.length
  const panelOpen = isMobile ? open : collapseOnDesktop ? open : true
  const panelClass = [
    'admin-collapsible-filters__panel',
    panelOpen ? 'is-open' : '',
    collapseOnDesktop ? 'admin-collapsible-filters__panel--desktop-collapsible' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="admin-collapsible-filters">
      {isMobile ? (
        <div className={`admin-collapsible-filters__bar${filtersOnly ? ' admin-collapsible-filters__bar--filters-only' : ''}`}>
          {quickSearch}
          {mobileActions}
          {activeChips.length > 0 ? (
            <div className="admin-collapsible-filters__chips" aria-label="Active filters">
              {activeChips.map((label) => (
                <span key={label} className="admin-collapsible-filters__chip">
                  {label}
                </span>
              ))}
            </div>
          ) : null}
          <button
            type="button"
            className="admin-collapsible-filters__toggle"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            Filters
            {count > 0 ? <span className="admin-collapsible-filters__badge">{count}</span> : null}
          </button>
        </div>
      ) : null}
      <div className={panelClass}>{children}</div>
    </div>
  )
}

export function useAdminMobileDefaultClosed() {
  const isMobile = useIsAdminMobile()
  return isMobile ? false : true
}
