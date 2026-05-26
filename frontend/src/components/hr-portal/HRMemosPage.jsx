import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function HRMemosPage() {
  const [memos, setMemos] = useState([])
  const [recipients, setRecipients] = useState([])
  const [recipientSearch, setRecipientSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ to_user_ids: [], subject: '', body: '', send_as_email: false })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function loadMemos() {
    const m = await apiFetch('/api/v1/hr/memos').catch(() => [])
    setMemos(m)
  }

  async function loadRecipients(q) {
    const qs = q?.trim() ? `?search=${encodeURIComponent(q.trim())}` : ''
    const rows = await apiFetch(`/api/v1/hr/recipients${qs}`).catch(() => [])
    setRecipients(Array.isArray(rows) ? rows : [])
  }

  useEffect(() => {
    setLoading(true)
    Promise.all([loadMemos(), loadRecipients('')]).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const t = setTimeout(() => loadRecipients(recipientSearch), 250)
    return () => clearTimeout(t)
  }, [recipientSearch])

  const filteredRecipients = useMemo(() => recipients, [recipients])

  function toggleRecipient(id) {
    setForm((prev) => ({
      ...prev,
      to_user_ids: prev.to_user_ids.includes(id)
        ? prev.to_user_ids.filter((x) => x !== id)
        : [...prev.to_user_ids, id],
    }))
  }

  function selectAllVisible() {
    setForm((prev) => ({ ...prev, to_user_ids: filteredRecipients.map((r) => r.id) }))
  }

  async function sendMemo(e) {
    e.preventDefault()
    if (!form.to_user_ids.length) {
      setError('Select at least one recipient.')
      return
    }
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const res = await apiFetch('/api/v1/hr/memos', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setForm({ to_user_ids: [], subject: '', body: '', send_as_email: false })
      setShowForm(false)
      setSuccess(res.email_sent ? 'Memo sent and emailed to recipients.' : 'Memo sent successfully.')
      loadMemos()
    } catch (err) {
      setError(err.message || 'Could not send memo')
    } finally {
      setSubmitting(false)
    }
  }

  const recipientName = (ids) => {
    if (!ids?.length) return '—'
    return ids
      .map((id) => recipients.find((t) => t.id === id)?.full_name || memosRecipientFallback(id))
      .join(', ')
  }

  function memosRecipientFallback(id) {
    return `#${id}`
  }

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '2rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28, gap: 12, flexWrap: 'wrap' }}>
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>HR</p>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Memos</h1>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>Send communications to therapists and staff.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setShowForm(!showForm)
            setError('')
            setSuccess('')
          }}
          style={{ padding: '8px 18px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}
        >
          {showForm ? 'Cancel' : '+ New memo'}
        </button>
      </div>

      {error ? <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>{error}</div> : null}
      {success ? <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#15803d', fontSize: '0.875rem' }}>{success}</div> : null}

      {showForm && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24, marginBottom: 20 }}>
          <p style={{ fontWeight: 600, marginBottom: 16 }}>Compose memo</p>
          <form onSubmit={sendMemo} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, gap: 8, flexWrap: 'wrap' }}>
                <p style={{ fontSize: '0.875rem', fontWeight: 500, margin: 0 }}>Recipients</p>
                <button type="button" onClick={selectAllVisible} style={{ fontSize: '0.75rem', color: '#6366f1', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                  Select all shown
                </button>
              </div>
              <input
                type="search"
                placeholder="Search staff or therapists…"
                value={recipientSearch}
                onChange={(e) => setRecipientSearch(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', marginBottom: 8, fontSize: '0.875rem' }}
              />
              {filteredRecipients.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>No recipients match. Try clearing search.</p>
              ) : (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, maxHeight: 180, overflowY: 'auto', padding: 8, border: '1px solid #d1d5db', borderRadius: 8 }}>
                  {filteredRecipients.map((t) => (
                    <label
                      key={t.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        padding: '4px 8px',
                        borderRadius: 20,
                        background: form.to_user_ids.includes(t.id) ? '#eef2ff' : '#f9fafb',
                        border: form.to_user_ids.includes(t.id) ? '1px solid #a5b4fc' : '1px solid #e5e7eb',
                      }}
                    >
                      <input type="checkbox" checked={form.to_user_ids.includes(t.id)} onChange={() => toggleRecipient(t.id)} />
                      {t.full_name}
                      <span style={{ color: '#9ca3af' }}>({t.kind})</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              Subject
              <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} required style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              Body
              <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} rows={5} required style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }} />
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem' }}>
              <input type="checkbox" checked={form.send_as_email} onChange={(e) => setForm({ ...form, send_as_email: e.target.checked })} />
              Also send as email (when SMTP is configured)
            </label>
            <button type="submit" disabled={submitting} style={{ padding: '10px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1 }}>
              {submitting ? 'Sending…' : `Send to ${form.to_user_ids.length || 0} recipient${form.to_user_ids.length !== 1 ? 's' : ''}`}
            </button>
          </form>
        </div>
      )}

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
      ) : memos.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', color: '#6b7280' }}>
          <p style={{ fontWeight: 600, marginBottom: 6 }}>No memos sent yet</p>
          <p style={{ fontSize: '0.875rem' }}>Use New memo to reach therapists and staff.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {memos.map((m) => (
            <div key={m.id} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <p style={{ fontWeight: 600, margin: 0 }}>{m.subject}</p>
                <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{new Date(m.created_at).toLocaleDateString()}</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 8 }}>To: {recipientName(m.to_user_ids)}</p>
              <p style={{ fontSize: '0.875rem', color: '#374151', whiteSpace: 'pre-wrap', margin: 0 }}>{m.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
