import { StatusBadge } from './ui/index.js'

export function AdminCaseDetailMobileHeader({ caseRow, activeAssignment }) {
  const therapistLabel =
    activeAssignment?.therapist_name ||
    (activeAssignment?.therapist_user_id ? `Therapist #${activeAssignment.therapist_user_id}` : null)

  return (
    <header className="admin-case-detail-summary admin-case-detail__mobile-only">
      <h1 className="admin-case-detail-summary__name">{caseRow.child_name}</h1>
      <p className="admin-case-detail-summary__code">{caseRow.case_code}</p>
      <div className="admin-case-detail-summary__row">
        <StatusBadge status={caseRow.status} />
        {caseRow.operational_stage ? (
          <span className="admin-chip" title="Operational stage">
            {caseRow.operational_stage}
          </span>
        ) : null}
        {caseRow.product_module ? (
          <span className="admin-chip">{caseRow.product_module}</span>
        ) : null}
      </div>
      {(caseRow.service_type || caseRow.case_manager_name || therapistLabel) && (
        <dl className="admin-case-detail-summary__meta">
          {caseRow.service_type ? (
            <>
              <dt>Type</dt>
              <dd>{caseRow.service_type}</dd>
            </>
          ) : null}
          {caseRow.case_manager_name ? (
            <>
              <dt>CM</dt>
              <dd>{caseRow.case_manager_name}</dd>
            </>
          ) : null}
          {therapistLabel ? (
            <>
              <dt>Therapist</dt>
              <dd>{therapistLabel}</dd>
            </>
          ) : null}
        </dl>
      )}
      {/* Intentionally no contact CTA chips on mobile header.
          Keep focus on builder/navigation actions below. */}
    </header>
  )
}
