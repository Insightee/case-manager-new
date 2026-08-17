import { useMemo } from 'react'
import { CaseBillingForm } from './CaseBillingForm.jsx'
import { billingSummary } from '../invoices/invoiceUtils.js'

/**
 * Step 1 of reassignment: re-enter billing for the incoming therapist.
 * Payload is held locally until reassignment confirms (preserves outgoing snapshot).
 */
export function ReassignmentBillingConfirm({
  caseItem,
  billingReady,
  onBillingReady,
  onBillingDraftChange,
  readOnly = false,
}) {
  const previousSummary = useMemo(
    () =>
      billingSummary({
        billing_type: caseItem?.billing_type,
        client_rate_per_session_inr: caseItem?.client_rate_per_session_inr,
        package_session_count: caseItem?.package_session_count,
        package_amount_inr: caseItem?.package_amount_inr,
        compensation_mode: caseItem?.compensation_mode,
        pay_share_amount_inr: caseItem?.pay_share_amount_inr,
        therapist_fixed_pay_inr: caseItem?.therapist_fixed_pay_inr,
      }),
    [caseItem],
  )

  function handleBillingSubmit(payload) {
    onBillingReady?.(payload)
    return Promise.resolve()
  }

  return (
    <div className="reassignment-billing-confirm" style={{ gridColumn: '1 / -1' }}>
      <p className="reassignment-billing-confirm__step">Step 1 of 2 — Billing for the new therapist</p>
      {previousSummary ? (
        <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 10 }}>
          Outgoing therapist terms (locked on reassignment): {previousSummary}
        </p>
      ) : null}
      <p className="admin-scheduling-hub__billing-note" style={{ marginBottom: 12 }}>
        Enter billing for the incoming therapist below, then choose Update billing. Reassignment unlocks after that.
      </p>
      {billingReady ? (
        <p className="admin-alert admin-alert--success" style={{ marginBottom: 12 }}>
          Billing ready for the new therapist. Continue to step 2 below.
        </p>
      ) : null}
      {!readOnly && !billingReady ? (
        <CaseBillingForm
          key={`reassign-billing-${caseItem?.id}-draft`}
          caseItem={caseItem}
          onSave={handleBillingSubmit}
          submitLabel="Update billing"
          blankSlate
        />
      ) : null}
      {!readOnly && billingReady ? (
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          onClick={() => onBillingDraftChange?.()}
        >
          Edit billing again
        </button>
      ) : null}
    </div>
  )
}

export const REASSIGNMENT_REASON_MIN = 5

export function isReassignmentReasonValid(reason) {
  return String(reason || '').trim().length >= REASSIGNMENT_REASON_MIN
}

export function FlagOutgoingTherapistCheckbox({ checked, onChange, disabled = false }) {
  return (
    <label
      className="admin-label"
      style={{
        alignItems: 'flex-start',
        display: 'flex',
        gap: 10,
        gridColumn: '1 / -1',
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        style={{ height: 18, marginTop: 2, width: 18 }}
      />
      <span>
        <strong>Flag this therapist</strong>
        <span className="admin-muted" style={{ display: 'block', marginTop: 3 }}>
          Show a private reminder to the payout team for this billing cycle. It
          clears after payment is processed.
        </span>
      </span>
    </label>
  )
}
