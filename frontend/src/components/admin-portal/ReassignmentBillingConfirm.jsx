import { useEffect, useMemo, useState } from 'react'
import { CaseBillingForm } from './CaseBillingForm.jsx'
import { billingSummary } from '../invoices/invoiceUtils.js'

/**
 * Billing verification step shown only when reassigning to a new therapist.
 */
export function ReassignmentBillingConfirm({
  caseItem,
  billingChoice,
  onBillingChoiceChange,
  onBillingPayloadChange,
  readOnly = false,
}) {
  const [localCase, setLocalCase] = useState(caseItem)

  useEffect(() => {
    setLocalCase(caseItem)
  }, [caseItem])

  const summary = useMemo(
    () =>
      billingSummary({
        billing_type: localCase?.billing_type,
        client_rate_per_session_inr: localCase?.client_rate_per_session_inr,
        package_session_count: localCase?.package_session_count,
        package_amount_inr: localCase?.package_amount_inr,
        compensation_mode: localCase?.compensation_mode,
        pay_share_amount_inr: localCase?.pay_share_amount_inr,
        therapist_fixed_pay_inr: localCase?.therapist_fixed_pay_inr,
      }),
    [localCase],
  )

  function handleFormSave(payload) {
    setLocalCase((prev) => ({ ...prev, ...payload }))
    onBillingPayloadChange?.(payload)
    return Promise.resolve()
  }

  return (
    <div className="reassignment-billing-confirm" style={{ gridColumn: '1 / -1' }}>
      <p className="admin-label" style={{ marginBottom: 8 }}>
        Billing for the new therapist
      </p>
      {summary ? (
        <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 10 }}>
          Current terms: {summary}
        </p>
      ) : (
        <p className="admin-scheduling-hub__billing-note" style={{ marginBottom: 10 }}>
          No billing configured yet — update below if needed.
        </p>
      )}
      <div className="admin-scheduling-hub__range" style={{ marginBottom: 12 }}>
        <label className="admin-scheduling-hub__range-option">
          <input
            type="radio"
            name="billingChoice"
            checked={billingChoice === 'keep'}
            onChange={() => onBillingChoiceChange?.('keep')}
            disabled={readOnly}
          />
          Keep same billing for the new therapist
        </label>
        <label className="admin-scheduling-hub__range-option">
          <input
            type="radio"
            name="billingChoice"
            checked={billingChoice === 'update'}
            onChange={() => onBillingChoiceChange?.('update')}
            disabled={readOnly}
          />
          Update billing for the new therapist
        </label>
      </div>
      {billingChoice === 'update' && !readOnly ? (
        <div style={{ borderTop: '1px solid var(--border, #e2e8f0)', paddingTop: 12 }}>
          <p className="admin-muted" style={{ fontSize: '0.8rem', marginBottom: 8 }}>
            Update the fields below and save billing, then confirm reassignment.
          </p>
          <CaseBillingForm
            caseItem={localCase}
            onSave={handleFormSave}
            readOnly={false}
          />
        </div>
      ) : null}
    </div>
  )
}

export const REASSIGNMENT_REASON_MIN = 5

export function isReassignmentReasonValid(reason) {
  return String(reason || '').trim().length >= REASSIGNMENT_REASON_MIN
}
