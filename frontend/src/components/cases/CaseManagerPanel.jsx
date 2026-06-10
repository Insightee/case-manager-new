import { Link } from 'react-router-dom'
import { therapistTicketsUrl } from '../../lib/therapistTicketOptions.js'

function initials(name) {
  if (!name) return '?'
  const parts = String(name).trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] || ''}${parts[parts.length - 1][0] || ''}`.toUpperCase()
}

export function CaseManagerPanel({ caseRow }) {
  const name = caseRow?.case_manager_name
  const email = caseRow?.case_manager_email
  const caseId = caseRow?.id
  const cmTicketUrl = therapistTicketsUrl({ topic: 'CASE_MANAGER', caseId, openForm: true })
  const supportUrl = therapistTicketsUrl({ openForm: true })

  return (
    <section className="ic-case-panel ic-case-panel--cm">
      <h3>Your case manager</h3>
      {name ? (
        <div className="ic-case-cm-card">
          <span className="ic-case-cm-card__avatar" aria-hidden>
            {initials(name)}
          </span>
          <div className="ic-case-cm-card__body">
            <p className="ic-case-cm-card__name">{name}</p>
            {email ? <span className="ic-case-cm-card__email">{email}</span> : null}
            <p className="ic-case-panel__hint">
              Raise a tracked ticket for log reviews, case changes, or clinical questions. Your case manager can reply
              in the support thread.
            </p>
            <div className="ic-case-cm-card__actions">
              <Link to={cmTicketUrl} className="ic-btn ic-btn--primary">
                Message case manager
              </Link>
              <Link to={supportUrl} className="ic-btn ic-btn--ghost">
                General support
              </Link>
            </div>
          </div>
        </div>
      ) : (
        <>
          <p className="ic-case-panel__hint">
            A case manager has not been assigned yet. You can still open a support ticket — link this case so the right
            team can follow up.
          </p>
          <div className="ic-case-cm-card__actions" style={{ marginTop: 10 }}>
            <Link to={cmTicketUrl} className="ic-btn ic-btn--primary">
              Open support ticket
            </Link>
          </div>
        </>
      )}
    </section>
  )
}
