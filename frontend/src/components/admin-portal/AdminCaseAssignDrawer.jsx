import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import {
  FlagOutgoingTherapistCheckbox,
  ReassignmentBillingConfirm,
  isReassignmentReasonValid,
} from './ReassignmentBillingConfirm.jsx'

export function AdminCaseAssignDrawer({ open, caseCard, onClose, onDone }) {
  const [therapistId, setTherapistId] = useState('')
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('')
  const [flagOutgoingTherapist, setFlagOutgoingTherapist] = useState(false)
  const [billingReady, setBillingReady] = useState(false)
  const [billingPayload, setBillingPayload] = useState(null)
  const [caseItem, setCaseItem] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const isReassignment = Boolean(caseCard?.therapist_name)

  useEffect(() => {
    if (!open || !caseCard?.id) return
    setReason('')
    setFlagOutgoingTherapist(false)
    setBillingReady(false)
    setBillingPayload(null)
    setError('')
    apiFetch(`/api/v1/cases/${caseCard.id}`)
      .then(setCaseItem)
      .catch(() => setCaseItem(null))
  }, [open, caseCard?.id])

  useEffect(() => {
    setBillingReady(false)
    setBillingPayload(null)
  }, [therapistId])

  if (!open || !caseCard) return null

  async function confirmAssignment(e) {
    e?.preventDefault()
    if (!therapistId) {
      setError('Select a therapist.')
      return
    }
    if (isReassignment && !isReassignmentReasonValid(reason)) {
      setError('Please add a reason for this reassignment (at least 5 characters).')
      return
    }
    if (isReassignment && !billingReady) {
      setError('Update billing for the new therapist before confirming reassignment.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const body = {
        therapist_user_id: Number(therapistId),
        start_date: startDate,
      }
      if (isReassignment) {
        body.reason_for_change = reason.trim()
        body.flag_outgoing_therapist = flagOutgoingTherapist
        if (billingPayload) {
          body.billing_update = billingPayload
        }
      }
      await apiFetch(`/api/v1/cases/${caseCard.id}/assignments`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      onDone?.()
      onClose()
    } catch (err) {
      setError(err.message || 'Assignment failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-drawer-backdrop" role="presentation" onClick={onClose}>
      <div className="admin-drawer" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3 className="admin-drawer__title">
          {isReassignment ? 'Reassign therapist' : 'Assign therapist'} — {caseCard.case_code}
        </h3>
        <p className="admin-muted" style={{ marginBottom: 16 }}>
          {caseCard.child_name || '—'} · {caseCard.service_type}
          {isReassignment && caseCard.therapist_name ? (
            <> · Current: <strong>{caseCard.therapist_name}</strong></>
          ) : null}
        </p>
        <form onSubmit={confirmAssignment} className="admin-form-grid" style={{ maxWidth: 480 }}>
          <label>
            Therapist
            <AdminTherapistPicker
              mode="allotment"
              productModule={caseCard.product_module}
              caseId={caseCard.id}
              value={therapistId}
              onChange={setTherapistId}
            />
          </label>
          <label>
            Start date
            <input
              type="date"
              className="admin-input"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </label>
          {isReassignment ? (
            <>
              <label style={{ gridColumn: '1 / -1' }} className="admin-label admin-label--stacked">
                <span className="admin-label__caption">
                  Reason for change <span className="admin-label__required" aria-hidden="true">*</span>
                </span>
                <input
                  type="text"
                  className="admin-input"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Caseload rebalance, therapist resigned"
                />
              </label>
              <FlagOutgoingTherapistCheckbox
                checked={flagOutgoingTherapist}
                onChange={setFlagOutgoingTherapist}
              />
              {caseItem ? (
                <ReassignmentBillingConfirm
                  caseItem={caseItem}
                  billingReady={billingReady}
                  onBillingReady={(payload) => {
                    setBillingPayload(payload)
                    setBillingReady(true)
                    setError('')
                  }}
                  onBillingDraftChange={() => {
                    setBillingReady(false)
                    setBillingPayload(null)
                  }}
                />
              ) : null}
            </>
          ) : null}
          {error ? <p className="admin-alert admin-alert--error" style={{ gridColumn: '1 / -1' }}>{error}</p> : null}
          <div style={{ display: 'flex', gap: 8, gridColumn: '1 / -1', flexWrap: 'wrap' }}>
            {isReassignment ? (
              billingReady ? (
                <>
                  <p className="reassignment-billing-confirm__step" style={{ width: '100%', margin: '0 0 4px' }}>
                    Step 2 of 2 — Confirm reassignment
                  </p>
                  <button
                    type="submit"
                    className="admin-btn admin-btn--primary"
                    disabled={busy || !isReassignmentReasonValid(reason)}
                  >
                    {busy ? 'Saving…' : 'Confirm reassignment'}
                  </button>
                </>
              ) : null
            ) : (
              <button type="submit" className="admin-btn admin-btn--primary" disabled={busy}>
                {busy ? 'Saving…' : 'Assign'}
              </button>
            )}
            <button type="button" className="admin-btn admin-btn--secondary" onClick={onClose} disabled={busy}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
