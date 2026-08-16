import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import {
  dayTypeLabel,
  isDayTypeChangeReasonValid,
  productRequiresDayType,
} from '../../lib/dayTypeLabels.js'
import { CaseBillingForm } from './CaseBillingForm.jsx'
import { billingSummary } from '../invoices/invoiceUtils.js'

export function CaseDayTypeSection({ caseItem, readOnly, canEdit, onCaseUpdated }) {
  const requiresDayType = productRequiresDayType(caseItem?.product_module)
  const currentDayType = caseItem?.day_type || ''
  const [selectedDayType, setSelectedDayType] = useState(currentDayType)
  const [reason, setReason] = useState('')
  const [updateBilling, setUpdateBilling] = useState(false)
  const [billingReady, setBillingReady] = useState(false)
  const [billingPayload, setBillingPayload] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    setSelectedDayType(currentDayType)
    setReason('')
    setUpdateBilling(false)
    setBillingReady(false)
    setBillingPayload(null)
    setError('')
    setSuccess('')
  }, [currentDayType, caseItem?.id])

  const isChanging = Boolean(currentDayType && selectedDayType && selectedDayType !== currentDayType)
  const isFirstSet = !currentDayType && Boolean(selectedDayType)
  const isDirty = selectedDayType !== currentDayType

  const previousSummary = useMemo(
    () =>
      billingSummary({
        billing_type: caseItem?.billing_type,
        client_rate_per_session_inr: caseItem?.client_rate_per_session_inr,
        client_monthly_rate_inr: caseItem?.client_monthly_rate_inr,
        package_session_count: caseItem?.package_session_count,
        package_amount_inr: caseItem?.package_amount_inr,
        compensation_mode: caseItem?.compensation_mode,
        pay_share_amount_inr: caseItem?.pay_share_amount_inr,
        therapist_fixed_pay_inr: caseItem?.therapist_fixed_pay_inr,
      }),
    [caseItem],
  )

  if (!requiresDayType) return null

  async function handleSave() {
    if (!selectedDayType) {
      setError('Select half day or full day for this case.')
      return
    }
    if (isChanging && !isDayTypeChangeReasonValid(reason)) {
      setError('Please add a reason for changing day type (at least 5 characters).')
      return
    }
    if (updateBilling && !billingReady) {
      setError('Update billing before saving, or turn off the billing update option.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const body = {
        day_type: selectedDayType,
        update_billing: updateBilling,
      }
      if (isChanging) body.reason = reason.trim()
      if (updateBilling && billingPayload) body.billing_update = billingPayload
      const updated = await apiFetch(`/api/v1/cases/${caseItem.id}/day-type`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      onCaseUpdated?.(updated)
      setSuccess(
        isFirstSet
          ? `Day type set to ${dayTypeLabel(selectedDayType)}.`
          : `Day type updated to ${dayTypeLabel(selectedDayType)}.`,
      )
    } catch (err) {
      setError(err.message || 'Could not update day type')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article id="case-school-day-type" className="admin-scheduling-hub__day-type card">
      <h3 style={{ fontWeight: 700, marginBottom: 12 }}>School day type</h3>
      {currentDayType ? (
        <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 12 }}>
          Current: <strong>{dayTypeLabel(currentDayType)}</strong>
        </p>
      ) : (
        <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 12 }}>
          Not set yet — choose half day or full day for this case.
        </p>
      )}
      <div className="admin-form-grid" style={{ maxWidth: 420 }}>
        <label style={{ gridColumn: '1 / -1' }}>
          Day type
          <select
            className="admin-input"
            value={selectedDayType}
            onChange={(e) => {
              setSelectedDayType(e.target.value)
              setBillingReady(false)
              setBillingPayload(null)
            }}
            disabled={readOnly || !canEdit}
          >
            <option value="">Select…</option>
            <option value="HALF_DAY">Half day</option>
            <option value="FULL_DAY">Full day</option>
          </select>
        </label>
        {isChanging ? (
          <label style={{ gridColumn: '1 / -1' }}>
            Reason for change
            <textarea
              className="admin-input"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is the day type changing?"
              disabled={readOnly || !canEdit}
            />
          </label>
        ) : null}
        {isChanging && canEdit && !readOnly ? (
          <label style={{ gridColumn: '1 / -1', display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={updateBilling}
              onChange={(e) => {
                setUpdateBilling(e.target.checked)
                if (!e.target.checked) {
                  setBillingReady(false)
                  setBillingPayload(null)
                }
              }}
            />
            Update billing for this change
          </label>
        ) : null}
      </div>
      {updateBilling && isChanging && canEdit && !readOnly ? (
        <div style={{ marginTop: 12 }}>
          {previousSummary ? (
            <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 10 }}>
              Current billing: {previousSummary}
            </p>
          ) : null}
          {!billingReady ? (
            <CaseBillingForm
              key={`day-type-billing-${caseItem.id}`}
              caseItem={caseItem}
              onSave={(payload) => {
                setBillingPayload(payload)
                setBillingReady(true)
                return Promise.resolve()
              }}
              submitLabel="Update billing"
              blankSlate
            />
          ) : (
            <p className="admin-alert admin-alert--success" style={{ marginBottom: 8 }}>
              Billing ready. Save the day type change below.
            </p>
          )}
        </div>
      ) : null}
      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}
      {canEdit && !readOnly && isDirty ? (
        <button type="button" className="admin-btn admin-btn--primary" disabled={busy} onClick={handleSave}>
          {busy ? 'Saving…' : isFirstSet ? 'Set day type' : 'Save day type change'}
        </button>
      ) : null}
    </article>
  )
}
