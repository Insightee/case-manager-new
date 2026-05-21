import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'

export function AdminBulkAssignModal({ open, caseCards, onClose, onDone }) {
  const [therapistId, setTherapistId] = useState('')
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('Bulk reassignment from pipeline')
  const [busy, setBusy] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  if (!open || !caseCards?.length) return null

  const productModule = caseCards[0]?.product_module

  async function submit(e) {
    e.preventDefault()
    if (!therapistId) {
      setError('Select a therapist.')
      return
    }
    setBusy(true)
    setError('')
    setResults(null)
    const succeeded = []
    const failed = []
    for (const card of caseCards) {
      try {
        await apiFetch(`/api/v1/cases/${card.id}/assignments`, {
          method: 'POST',
          body: JSON.stringify({
            therapist_user_id: Number(therapistId),
            start_date: startDate,
            reason_for_change: reason,
          }),
        })
        succeeded.push(card.case_code)
      } catch (err) {
        failed.push({ code: card.case_code, message: err.message || 'Failed' })
      }
    }
    setResults({ succeeded, failed })
    setBusy(false)
    if (failed.length === 0) {
      onDone?.()
      onClose()
    }
  }

  return (
    <div className="admin-drawer-backdrop" role="presentation" onClick={onClose}>
      <div className="admin-drawer" style={{ maxWidth: 480 }} role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h3 className="admin-drawer__title">Bulk assign therapist</h3>
        <p className="admin-muted" style={{ marginBottom: 16 }}>
          {caseCards.length} case{caseCards.length === 1 ? '' : 's'} selected
        </p>
        <form onSubmit={submit} className="admin-form-grid">
          <label>
            Therapist
            <AdminTherapistPicker
              mode="allotment"
              productModule={productModule}
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
          {results ? (
            <div style={{ fontSize: '0.85rem' }}>
              {results.succeeded.length > 0 ? (
                <p style={{ color: '#059669' }}>Assigned: {results.succeeded.join(', ')}</p>
              ) : null}
              {results.failed.length > 0 ? (
                <ul style={{ color: '#b91c1c', paddingLeft: 18 }}>
                  {results.failed.map((f) => (
                    <li key={f.code}>
                      {f.code}: {f.message}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={busy}>
              {busy ? 'Assigning…' : `Assign to ${caseCards.length} cases`}
            </button>
            <button type="button" className="admin-btn admin-btn--secondary" onClick={onClose} disabled={busy}>
              {results?.failed?.length ? 'Close' : 'Cancel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
