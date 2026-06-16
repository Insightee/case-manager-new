import { Link } from 'react-router-dom'

export function ClientCaseAccessModal({ family, open, onClose }) {
  const allCases = family?.cases?.filter((c) => c.caseId) || []
  const activeCases = allCases.filter((c) => c.status !== 'CLOSED')

  if (!open || !family) return null

  return (
    <div className="admin-drawer-backdrop" role="presentation" onClick={onClose}>
      <div
        className="admin-drawer admin-drawer--wide"
        role="dialog"
        aria-labelledby="client-case-access-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="admin-drawer__header">
          <h2 id="client-case-access-title" className="admin-drawer__title">
            Active cases — {family.childName}
          </h2>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onClose}>
            Close
          </button>
        </header>
        <div className="admin-drawer__body">
          {activeCases.length === 0 ? (
            <p className="admin-muted">
              {allCases.length === 0
                ? 'No cases linked yet. Allot a case from the Cases board.'
                : 'No active cases'}
            </p>
          ) : (
            <ul className="admin-stack" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {activeCases.map((c) => (
                <li
                  key={c.caseId}
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    alignItems: 'center',
                    padding: '12px 0',
                    borderBottom: '1px solid var(--admin-border, #e2e8f0)',
                  }}
                >
                  <span style={{ minWidth: 120, fontWeight: 600 }}>{c.caseCode}</span>
                  <span className="admin-chip">{c.status?.replaceAll('_', ' ') || '—'}</span>
                  <Link
                    to={`/admin/cases/${c.caseId}`}
                    className="admin-btn admin-btn--primary admin-btn--sm"
                    onClick={onClose}
                  >
                    View case
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
