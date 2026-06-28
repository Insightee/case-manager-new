import { Link } from 'react-router-dom'
import { StatusBadge } from './StatusBadge.jsx'

function clientInitials(name) {
  const parts = String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] || ''}${parts[parts.length - 1][0] || ''}`.toUpperCase()
}

function dueTone(caseRow) {
  if (caseRow.critical || caseRow.needsLogCount > 0) return 'urgent'
  const due = String(caseRow.nextDue || '').toLowerCase()
  if (due.includes('log') || due.includes('report') || due.includes('due')) return 'warn'
  return 'normal'
}

export function MyCasesTable({ cases }) {
  return (
    <div className="ic-cases-table-card">
      <div className="ic-cases-table-card__head">
        <h3 className="ic-cases-table-card__title">All cases</h3>
        <span className="ic-cases-table-card__count">{cases.length} assigned</span>
      </div>
      <div className="ic-cases-table-wrap">
        <table className="ic-cases-table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Service</th>
              <th>Visit address</th>
              <th>Stage</th>
              <th>Next due</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {cases.length === 0 ? (
              <tr>
                <td colSpan={6} className="ic-cases-table-empty">
                  No cases match your search or filters.
                </td>
              </tr>
            ) : (
              cases.map((c) => {
                const tone = dueTone(c)
                return (
                  <tr key={c.id}>
                    <td>
                      <div className="ic-cases-table__client">
                        <span className="ic-cases-table__avatar" aria-hidden>
                          {clientInitials(c.child)}
                        </span>
                        <div className="ic-cases-table__client-meta">
                          <span className="ic-cases-table__child">{c.child}</span>
                          <Link to={`/therapist/cases/${c.id}`} className="ic-cases-table__case-link">
                            {c.caseId}
                          </Link>
                        </div>
                      </div>
                    </td>
                    <td className="ic-cases-table__service">{c.service}</td>
                    <td className="ic-cases-table__address">
                      {c.serviceAddress?.formatted ? (
                        <>
                          <span>{c.serviceAddress.formatted}</span>
                          {c.mapsUrl ? (
                            <a href={c.mapsUrl} target="_blank" rel="noopener noreferrer">
                              Maps
                            </a>
                          ) : null}
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <StatusBadge variant={c.badgeVariant}>{c.stage}</StatusBadge>
                    </td>
                    <td>
                      <span
                        className={`ic-cases-table__due${
                          tone === 'urgent'
                            ? ' ic-cases-table__due--urgent'
                            : tone === 'warn'
                              ? ' ic-cases-table__due--warn'
                              : ''
                        }`}
                      >
                        {c.nextDue}
                      </span>
                    </td>
                    <td>
                      <div className="ic-cases-table__actions">
                        <Link
                          to="/therapist/logs"
                          className="ic-cases-table__action ic-cases-table__action--primary"
                        >
                          Session log
                        </Link>
                        <Link
                          to={`/therapist/cases/${c.id}`}
                          className="ic-cases-table__action ic-cases-table__action--ghost"
                        >
                          View
                        </Link>
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
