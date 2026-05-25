import { Link } from 'react-router-dom'

export function CaseManagerPanel({ caseRow }) {
  const name = caseRow?.case_manager_name
  const email = caseRow?.case_manager_email

  return (
    <section className="ic-case-panel ic-case-panel--cm">
      <h3>Your case manager</h3>
      {name ? (
        <>
          <p className="ic-case-panel__line">
            <strong>{name}</strong>
          </p>
          {email ? (
            <p className="ic-case-panel__line">
              <a href={`mailto:${email}`}>{email}</a>
            </p>
          ) : null}
          <p className="ic-case-panel__hint">
            Reach out for log reviews, case changes, or clinical questions.
          </p>
        </>
      ) : (
        <p className="ic-case-panel__hint">
          A case manager has not been assigned yet. Use Contact support for urgent help.
        </p>
      )}
      <Link to="/therapist/tickets" className="ic-btn ic-btn--ghost" style={{ marginTop: 10 }}>
        Contact support
      </Link>
    </section>
  )
}
