import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminPanel, formatCurrency } from './ui/index.js'

function defaultMonth() {
  return new Date().toISOString().slice(0, 7)
}

export function TherapistPayoutRaisePanel() {
  const { canWriteBilling } = useModuleWrite()
  const [month, setMonth] = useState(defaultMonth())
  const [search, setSearch] = useState('')
  const [therapists, setTherapists] = useState([])
  const [therapistId, setTherapistId] = useState('')
  const [preview, setPreview] = useState(null)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const q = new URLSearchParams()
    if (search.trim()) q.set('search', search.trim())
    if (month) q.set('month', month)
    apiFetch(`/api/v1/invoices/payout-therapists?${q}`)
      .then((rows) => setTherapists(Array.isArray(rows) ? rows : []))
      .catch(() => setTherapists([]))
  }, [search, month])

  async function loadPreview() {
    if (!therapistId) return
    setLoading(true)
    setError('')
    setMessage('')
    try {
      const data = await apiFetch(
        `/api/v1/invoices/preview?month=${encodeURIComponent(month)}&therapist_user_id=${therapistId}`,
      )
      setPreview(data)
    } catch (err) {
      setPreview(null)
      setError(err.message || 'Could not load the system amount for this therapist.')
    } finally {
      setLoading(false)
    }
  }

  async function raiseInvoice() {
    if (!therapistId) return
    setActing(true)
    setError('')
    setMessage('')
    try {
      const inv = await apiFetch('/api/v1/invoices/submit-for-therapist', {
        method: 'POST',
        body: JSON.stringify({
          therapist_user_id: Number(therapistId),
          month,
          notes: notes.trim() || 'Raised by finance',
        }),
      })
      setMessage(`Invoice #${inv.id} is in review for ${inv.therapist_name || 'the therapist'}.`)
      setPreview(null)
      setNotes('')
    } catch (err) {
      setError(err.message || 'Could not raise this payout invoice.')
    } finally {
      setActing(false)
    }
  }

  const selected = therapists.find((t) => String(t.id) === String(therapistId))

  return (
    <AdminPanel title="Raise a payout invoice" padded style={{ marginBottom: 16 }}>
      <p className="admin-muted" style={{ marginTop: 0 }}>
        Use this when a therapist has not submitted for the month. The amount comes from the same cycle engine they would see — it does not change parent billing.
      </p>
      <div className="admin-form-grid" style={{ gridTemplateColumns: '140px 1fr auto', gap: 10, marginBottom: 12 }}>
        <input
          className="admin-input"
          type="month"
          value={month}
          onChange={(e) => {
            setMonth(e.target.value)
            setPreview(null)
          }}
          aria-label="Billing month"
        />
        <input
          className="admin-input"
          placeholder="Search therapist…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={!therapistId || loading} onClick={loadPreview}>
          {loading ? 'Loading…' : 'Show amount'}
        </button>
      </div>
      <select
        className="admin-select"
        value={therapistId}
        onChange={(e) => {
          setTherapistId(e.target.value)
          setPreview(null)
          setMessage('')
        }}
        style={{ width: '100%', marginBottom: 12 }}
      >
        <option value="">Select therapist</option>
        {therapists.map((t) => (
          <option key={t.id} value={t.id}>
            {t.fullName}
            {t.hasInvoiceThisMonth ? ' · already has an invoice' : ''}
          </option>
        ))}
      </select>
      {selected?.hasInvoiceThisMonth ? (
        <p className="admin-alert admin-alert--warning">This therapist already has a payout invoice for {month}.</p>
      ) : null}
      {preview ? (
        <div className="client-inv-overview__totals-grid" style={{ marginBottom: 12 }}>
          <div>
            <span className="client-inv-overview__k">Gross (system)</span>
            <strong>{formatCurrency(preview.subtotal_inr ?? preview.net_amount_inr)}</strong>
          </div>
          <div>
            <span className="client-inv-overview__k">Sessions</span>
            <strong>{preview.total_sessions ?? 0}</strong>
          </div>
          <div>
            <span className="client-inv-overview__k">Net before TDS</span>
            <strong>{formatCurrency(preview.net_amount_inr)}</strong>
          </div>
        </div>
      ) : null}
      <textarea
        className="admin-input"
        rows={2}
        placeholder="Note for the therapist (optional)"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        style={{ width: '100%', marginBottom: 12 }}
      />
      {error ? <p className="admin-alert admin-alert--warning">{error}</p> : null}
      {message ? <p className="admin-alert admin-alert--success">{message}</p> : null}
      {canWriteBilling ? (
        <button
          type="button"
          className="admin-btn admin-btn--primary admin-btn--sm"
          disabled={acting || !therapistId || selected?.hasInvoiceThisMonth}
          onClick={raiseInvoice}
        >
          {acting ? 'Raising…' : 'Raise invoice'}
        </button>
      ) : null}
    </AdminPanel>
  )
}
