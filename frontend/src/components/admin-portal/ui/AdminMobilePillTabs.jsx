import { useEffect, useId, useRef, useState } from 'react'

/**
 * Mobile-only pill tab bar with optional overflow "More" menu.
 * Preserves tab ids — only changes presentation.
 */
export function AdminMobilePillTabs({
  tabs,
  activeId,
  onChange,
  primaryIds,
  overflowIds,
  ariaLabel = 'Sections',
  className = '',
}) {
  const moreId = useId()
  const [moreOpen, setMoreOpen] = useState(false)
  const wrapRef = useRef(null)

  const primarySet = new Set(primaryIds)
  const overflowSet = new Set(overflowIds)
  const primaryTabs = tabs.filter((t) => primarySet.has(t.id))
  const overflowTabs = tabs.filter((t) => overflowSet.has(t.id))
  const overflowActive = overflowSet.has(activeId)

  useEffect(() => {
    if (!moreOpen) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') setMoreOpen(false)
    }
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setMoreOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDoc)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDoc)
    }
  }, [moreOpen])

  return (
    <nav
      ref={wrapRef}
      className={`admin-mobile-pill-tabs admin-mobile-only ${className}`.trim()}
      aria-label={ariaLabel}
    >
      <div className="admin-mobile-pill-tabs__row" role="tablist">
        {primaryTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={activeId === t.id}
            className={`admin-mobile-pill-tabs__pill${activeId === t.id ? ' is-active' : ''}`}
            onClick={() => onChange(t.id)}
          >
            {t.label}
            {t.badge != null && t.badge !== '' ? (
              <span className="admin-mobile-pill-tabs__badge">{t.badge}</span>
            ) : null}
          </button>
        ))}
        {overflowTabs.length > 0 ? (
          <div className="admin-mobile-pill-tabs__more-wrap">
            <button
              type="button"
              className={`admin-mobile-pill-tabs__pill admin-mobile-pill-tabs__more${overflowActive ? ' is-active' : ''}`}
              aria-expanded={moreOpen}
              aria-haspopup="menu"
              aria-controls={moreId}
              onClick={() => setMoreOpen((v) => !v)}
            >
              More ▾
            </button>
            {moreOpen ? (
              <ul id={moreId} className="admin-mobile-pill-tabs__menu" role="menu">
                {overflowTabs.map((t) => (
                  <li key={t.id} role="none">
                    <button
                      type="button"
                      role="menuitem"
                      className={activeId === t.id ? 'is-active' : ''}
                      onClick={() => {
                        onChange(t.id)
                        setMoreOpen(false)
                      }}
                    >
                      {t.label}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </div>
    </nav>
  )
}
