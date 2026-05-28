import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'

export function AdminCaseDetailFab({ caseId, visibleTabIds, onSelectTab, canInvoice }) {
  const [open, setOpen] = useState(false)
  const titleId = useId()
  const visible = new Set(visibleTabIds)

  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  function pickTab(id) {
    setOpen(false)
    onSelectTab(id)
  }

  const actions = [
    visible.has('logs')
      ? { key: 'log', label: 'Add session log', onClick: () => pickTab('logs') }
      : null,
    visible.has('reports')
      ? { key: 'report', label: 'Upload report', onClick: () => pickTab('reports') }
      : null,
    visible.has('scheduling')
      ? { key: 'schedule', label: 'Schedule meeting', onClick: () => pickTab('scheduling') }
      : visible.has('cm-meetings')
        ? { key: 'cm', label: 'Schedule meeting', onClick: () => pickTab('cm-meetings') }
        : null,
    canInvoice && visible.has('billing')
      ? { key: 'invoice', label: 'Raise invoice', onClick: () => pickTab('billing') }
      : canInvoice
        ? {
            key: 'invoice-hub',
            label: 'Raise invoice',
            href: `/admin/invoices?case_id=${caseId}`,
          }
        : null,
  ].filter(Boolean)

  if (actions.length === 0) return null

  return (
    <div className="admin-case-detail__mobile-only">
      <button
        type="button"
        className="admin-case-detail-fab"
        aria-label="Case quick actions"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        +
      </button>
      {open ? (
        <>
          <button
            type="button"
            className="admin-case-detail-fab-sheet__backdrop"
            aria-label="Close actions menu"
            onClick={() => setOpen(false)}
          />
          <div
            className="admin-case-detail-fab-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
          >
            <p id={titleId} className="admin-case-detail-fab-sheet__title">
              Quick actions
            </p>
            <ul className="admin-case-detail-fab-sheet__actions">
              {actions.map((a) => (
                <li key={a.key}>
                  {a.href ? (
                    <Link to={a.href} onClick={() => setOpen(false)}>
                      {a.label}
                    </Link>
                  ) : (
                    <button type="button" onClick={a.onClick}>
                      {a.label}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </div>
  )
}
