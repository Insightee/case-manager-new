import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const MODULES = [
  { value: 'homecare', label: 'Homecare' },
  { value: 'shadow_support', label: 'Shadow support' },
]

export function NewClientIntakeForm({ onCreated, onCancel, disabled }) {
  const [form, setForm] = useState({
    client_name: '',
    child_name: '',
    client_email: '',
    client_phone: '',
    product_module: 'homecare',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function setField(k, v) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.client_name.trim() || !form.child_name.trim() || !form.client_email.trim()) {
      setError('Parent name, child name, and email are required.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const result = await apiFetch('/api/v1/therapist/client-intake', {
        method: 'POST',
        body: JSON.stringify({
          client_name: form.client_name.trim(),
          child_name: form.child_name.trim(),
          client_email: form.client_email.trim(),
          client_phone: form.client_phone.trim() || undefined,
          product_module: form.product_module,
        }),
      })
      onCreated?.(result)
    } catch (err) {
      setError(err.message || 'Could not create client')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="ic-new-client-intake" onSubmit={submit}>
      <p className="ic-session-composer__sub" style={{ marginTop: 0 }}>
        Create a provisional case. The parent invite email is sent when you start the first session.
      </p>
      <div className="ic-session-composer__grid">
        <label className="ic-session-composer__field">
          <span>Parent / guardian name</span>
          <input
            className="ic-session-composer__input"
            value={form.client_name}
            onChange={(e) => setField('client_name', e.target.value)}
            required
          />
        </label>
        <label className="ic-session-composer__field">
          <span>Child name</span>
          <input
            className="ic-session-composer__input"
            value={form.child_name}
            onChange={(e) => setField('child_name', e.target.value)}
            required
          />
        </label>
        <label className="ic-session-composer__field">
          <span>Parent email</span>
          <input
            type="email"
            className="ic-session-composer__input"
            value={form.client_email}
            onChange={(e) => setField('client_email', e.target.value)}
            required
          />
        </label>
        <label className="ic-session-composer__field">
          <span>Phone (optional)</span>
          <input
            className="ic-session-composer__input"
            value={form.client_phone}
            onChange={(e) => setField('client_phone', e.target.value)}
          />
        </label>
        <label className="ic-session-composer__field">
          <span>Service line</span>
          <select
            className="ic-session-composer__input"
            value={form.product_module}
            onChange={(e) => setField('product_module', e.target.value)}
          >
            {MODULES.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error ? <p className="ic-session-composer__error">{error}</p> : null}
      <div className="ic-session-composer__actions">
        <button type="submit" className="ic-btn ic-btn--primary" disabled={busy || disabled}>
          {busy ? 'Creating…' : 'Create client'}
        </button>
        {onCancel ? (
          <button type="button" className="ic-btn ic-btn--ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  )
}
