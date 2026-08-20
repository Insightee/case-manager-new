import { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminPanel, formatCurrency } from './ui/index.js'
import './admin-therapist-picker.css'

function defaultMonth() {
  return new Date().toISOString().slice(0, 7)
}

function therapistMatches(t, query) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const hay = `${t.fullName || ''} ${t.email || ''} ${t.id || ''}`.toLowerCase()
  return q.split(/\s+/).filter(Boolean).every((tok) => hay.includes(tok))
}

export function TherapistPayoutRaisePanel() {
  const { canWriteBilling } = useModuleWrite()
  const wrapRef = useRef(null)
  const [month, setMonth] = useState(defaultMonth())
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [therapists, setTherapists] = useState([])
  const [listLoading, setListLoading] = useState(false)
  const [listError, setListError] = useState('')
  const [selected, setSelected] = useState(null)
  const [preview, setPreview] = useState(null)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 250)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    const q = new URLSearchParams()
    if (debouncedSearch) q.set('search', debouncedSearch)
    if (month) q.set('month', month)
    setListLoading(true)
    setListError('')
    apiFetch(`/api/v1/invoices/payout-therapists?${q}`)
      .then((rows) => setTherapists(Array.isArray(rows) ? rows : []))
      .catch(() => {
        setTherapists([])
        setListError('Could not load therapists. Refresh and try again.')
      })
      .finally(() => setListLoading(false))
  }, [debouncedSearch, month])

  useEffect(() => {
    function onDoc(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const matches = useMemo(
    () => therapists.filter((t) => therapistMatches(t, search)),
    [therapists, search],
  )

  function pickTherapist(t) {
    setSelected(t)
    setSearch('')
    setOpen(false)
    setPreview(null)
    setMessage('')
    setError('')
  }

  function clearTherapist() {
    setSelected(null)
    setPreview(null)
    setMessage('')
    setError('')
  }

  async function loadPreview() {
    if (!selected?.id) return
    setLoading(true)
    setError('')
    setMessage('')
    try {
      const data = await apiFetch(
        `/api/v1/invoices/preview?month=${encodeURIComponent(month)}&therapist_user_id=${selected.id}`,
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
    if (!selected?.id) return
    setActing(true)
    setError('')
    setMessage('')
    try {
      const inv = await apiFetch('/api/v1/invoices/submit-for-therapist', {
        method: 'POST',
        body: JSON.stringify({
          therapist_user_id: Number(selected.id),
          month,
          notes: notes.trim() || 'Raised by finance',
        }),
      })
      setMessage(`Invoice #${inv.id} is in review for ${inv.therapist_name || selected.fullName}.`)
      setPreview(null)
      setNotes('')
    } catch (err) {
      setError(err.message || 'Could not raise this payout invoice.')
    } finally {
      setActing(false)
    }
  }

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
        <div ref={wrapRef} className="admin-therapist-picker" style={{ marginBottom: 0 }}>
          {selected ? (
            <div className="admin-therapist-picker__selected">
              <span className="admin-therapist-picker__selected-text">
                <strong>{selected.fullName}</strong>
                <span>{selected.email || `ID #${selected.id}`}</span>
              </span>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={clearTherapist}>
                Change
              </button>
            </div>
          ) : (
            <>
              <input
                className="admin-input"
                type="search"
                placeholder="Search therapist by name or email…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value)
                  setOpen(true)
                }}
                onFocus={() => setOpen(true)}
                aria-label="Search therapist"
                autoComplete="off"
              />
              {open ? (
                <div className="admin-therapist-picker__menu" role="listbox">
                  {listLoading ? <p className="admin-muted" style={{ margin: 8, fontSize: '0.85rem' }}>Loading therapists…</p> : null}
                  {listError ? <p className="admin-therapist-picker__hint admin-therapist-picker__hint--warn">{listError}</p> : null}
                  {!listLoading && !listError && matches.length === 0 ? (
                    <p className="admin-therapist-picker__hint admin-therapist-picker__hint--warn">
                      No therapists match. Try another name or email.
                    </p>
                  ) : null}
                  {!listLoading
                    ? matches.map((t) => (
                        <button
                          key={t.id}
                          type="button"
                          role="option"
                          className="admin-therapist-picker__card"
                          onClick={() => pickTherapist(t)}
                        >
                          <span className="admin-therapist-picker__card-body">
                            <span className="admin-therapist-picker__name">{t.fullName}</span>
                            <span className="admin-therapist-picker__email">{t.email || `ID #${t.id}`}</span>
                            {t.hasInvoiceThisMonth ? (
                              <span className="admin-therapist-picker__already">Already has an invoice this month</span>
                            ) : null}
                          </span>
                        </button>
                      ))
                    : null}
                </div>
              ) : null}
            </>
          )}
        </div>
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          disabled={!selected || loading}
          onClick={loadPreview}
        >
          {loading ? 'Loading…' : 'Show amount'}
        </button>
      </div>
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
          disabled={acting || !selected || selected?.hasInvoiceThisMonth}
          onClick={raiseInvoice}
        >
          {acting ? 'Raising…' : 'Raise invoice'}
        </button>
      ) : null}
    </AdminPanel>
  )
}
