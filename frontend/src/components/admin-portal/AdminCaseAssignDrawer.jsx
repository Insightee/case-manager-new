import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'

export function AdminCaseAssignDrawer({ open, caseCard, onClose, onDone }) {
  const [therapistId, setTherapistId] = useState('')
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('Pipeline reassignment')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!open || !caseCard) return null

  async function submit(e) {
    e.preventDefault()
    if (!therapistId) {
      setError('Select a therapist.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await apiFetch(`/api/v1/cases/${caseCard.id}/assignments`, {
        method: 'POST',
        body: JSON.stringify({
          therapist_user_id: Number(therapistId),
          start_date: startDate,
          reason_for_change: reason,
        }),
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
          Assign therapist — {caseCard.case_code}
        </h3>
        <p className="admin-muted" style={{ marginBottom: 16 }}>
          {caseCard.child_name || '—'} · {caseCard.service_type}
        </p>
        <form onSubmit={submit} className="admin-form-grid" style={{ maxWidth: 420 }}>
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
          <label>
            Reason
            <input
              type="text"
              className="admin-input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={busy}>
              {busy ? 'Assigning…' : 'Assign'}
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
