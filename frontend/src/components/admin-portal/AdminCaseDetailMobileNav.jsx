/** Mobile/tablet case detail navigation — presentation only; uses existing tab ids. */

const PRIMARY_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'activity', label: 'Timeline' },
  { id: 'logs', label: 'Sessions' },
  { id: 'reports', label: 'Reports' },
]

const SECONDARY_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'activity', label: 'Timeline' },
  { id: 'logs', label: 'Sessions' },
  { id: 'reports', label: 'Reports' },
  { id: 'documents', label: 'Documents' },
  { id: 'iep', label: 'IEP' },
  { id: 'billing', label: 'Billing' },
  { id: 'scheduling', label: 'Scheduling' },
  { id: 'cm-meetings', label: 'Meetings' },
  { id: 'assignments', label: 'Assignments' },
]

export function AdminCaseDetailMobileNav({ activeId, onChange, visibleTabIds }) {
  const visible = new Set(visibleTabIds)
  const primary = PRIMARY_TABS.filter((t) => visible.has(t.id))
  const secondary = SECONDARY_TABS.filter((t) => visible.has(t.id))
  const primaryActive = primary.some((t) => t.id === activeId)

  return (
    <nav className="admin-case-detail__mobile-nav admin-case-detail__mobile-only" aria-label="Case sections">
      <div className="admin-case-detail__primary-tabs" role="tablist" aria-label="Primary sections">
        {primary.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`case-tab-${t.id}`}
            aria-selected={activeId === t.id}
            className={activeId === t.id ? 'is-active' : ''}
            onClick={() => onChange(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {secondary.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <p className="admin-case-detail__quick-actions-label">Quick actions</p>
          <div className="admin-case-detail__quick-actions" role="group" aria-label="More case modules">
            {secondary.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`admin-case-detail__quick-action${activeId === t.id ? ' is-active' : ''}`}
                aria-current={activeId === t.id ? 'page' : undefined}
                onClick={() => onChange(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {!primaryActive && secondary.some((t) => t.id === activeId) ? (
        <span className="visually-hidden" aria-live="polite">
          Viewing {secondary.find((t) => t.id === activeId)?.label}
        </span>
      ) : null}
    </nav>
  )
}
