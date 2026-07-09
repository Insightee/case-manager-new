import { useEffect, useRef, useState } from 'react'

const CREATE_ICONS = {
  observation_report: 'visibility',
  monthly_report: 'calendar_month',
  iep: 'psychology',
  progress_report: 'trending_up',
  cm_meeting_note: 'groups',
}

export function CaseReportsHeader({ createActions = [], onCreate, compact = false }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  return (
    <header className={`crt-header${compact ? ' crt-header--compact' : ''}`}>
      <div className="crt-header__copy">
        <h1 className="crt-header__title">Reports</h1>
      </div>
      <div className="crt-header__actions" ref={rootRef}>
        <button
          type="button"
          className={compact ? 'crt-header__create crt-header__create--pill' : 'crt-header__create'}
          aria-expanded={open}
          aria-haspopup="menu"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="material-symbols-outlined" aria-hidden="true">
            {compact ? 'add' : 'add_circle'}
          </span>
          {compact ? 'New Draft' : 'Add / Create Report'}
          {!compact ? (
            <span className="material-symbols-outlined crt-header__chevron" aria-hidden="true">
              expand_more
            </span>
          ) : null}
        </button>
        {open ? (
          <div className="crt-header__menu" role="menu">
            {createActions.map((action) => (
              <button
                key={action.type}
                type="button"
                role="menuitem"
                className="crt-header__menu-item"
                onClick={() => {
                  setOpen(false)
                  onCreate?.(action)
                }}
              >
                <span className="material-symbols-outlined" aria-hidden="true">
                  {CREATE_ICONS[action.type] || 'description'}
                </span>
                {action.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </header>
  )
}
