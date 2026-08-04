import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { ReassignmentBillingConfirm, isReassignmentReasonValid } from './ReassignmentBillingConfirm.jsx'

export function AdminCaseAssignDrawer({ open, caseCard, onClose, onDone }) {
  const [therapistId, setTherapistId] = useState('')
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('')
  const [billingChoice, setBillingChoice] = useState('keep')
  const [billingPayload, setBillingPayload] = useState(null)
  const [caseItem, setCaseItem] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const isReassignment = Boolean(caseCard?.therapist_name)

  useEffect(() => {
    if (!open || !caseCard?.id) return
    setReason('')
    setBillingChoice('keep')
    setBillingPayload(null)
    setError('')
    apiFetch(`/api/v1/cases/${caseCard.id}`)
      .then(setCaseItem)
      .catch(() => setCaseItem(null))
  }, [open, caseCard?.id])

  if (!open || !caseCard) return null

  async function submit(e) {
    e.preventDefault()
    if (!therapistId) {
      setError('Select a therapist.')
      return
    }
    if (isReassignment && !isReassignmentReasonValid(reason)) {
      setError('Please add a reason for this reassignment (at least 5 characters).')
      return
    }
    if (isReassignment && billingChoice === 'update' && !billingPayload) {
      setError('Save the updated billing terms before confirming.')
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
        if (billingChoice === 'update' && billingPayload) {
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
        <form onSubmit={submit} className="admin-form-grid" style={{ maxWidth: 480 }}>
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
              <label style={{ gridColumn: '1 / -1' }}>
                Reason for change <span style={{ color: '#ef4444' }}>*</span>
                <input
                  type="text"
                  className="admin-input"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Caseload rebalance, therapist resigned"
                />
              </label>
              {caseItem ? (
                <ReassignmentBillingConfirm
                  caseItem={caseItem}
                  billingChoice={billingChoice}
                  onBillingChoiceChange={setBillingChoice}
                  onBillingPayloadChange={setBillingPayload}
                />
              ) : null}
            </>
          ) : null}
          {error ? <p className="admin-alert admin-alert--error" style={{ gridColumn: '1 / -1' }}>{error}</p> : null}
          <div style={{ display: 'flex', gap: 8, gridColumn: '1 / -1' }}>
            <button
              type="submit"
              className="admin-btn admin-btn--primary"
              disabled={busy || (isReassignment && !isReassignmentReasonValid(reason))}
            >
              {busy ? 'Saving…' : isReassignment ? 'Confirm reassignment' : 'Assign'}
            </button>
            <button type="button" className="admin-btn admin-btn--secondary" onClick={onClose} disabled={busy}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
