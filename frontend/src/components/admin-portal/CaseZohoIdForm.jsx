import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function CaseZohoIdForm({ caseItem, canEdit, onSaved }) {
  const [value, setValue] = useState(caseItem?.zoho_id || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setValue(caseItem?.zoho_id || '')
    setError('')
    setSaved(false)
  }, [caseItem?.id, caseItem?.zoho_id])

  if (!caseItem) return null

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canEdit) return
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const updated = await apiFetch(`/api/v1/cases/${caseItem.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ zoho_id: value.trim() || null }),
      })
      onSaved?.(updated)
      setSaved(true)
    } catch (err) {
      setError(err.message || 'Looks like we still need a moment before we can save this Zoho ID.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="admin-panel" style={{ padding: 16 }} onSubmit={handleSubmit}>
      <h3 style={{ marginTop: 0 }}>Zoho ID</h3>
      <p className="admin-muted" style={{ marginTop: 0, fontSize: '0.8rem' }}>
        Client billing identifier. Stored on this case for later Zoho Pay — not used for invoices yet.
      </p>
      <label htmlFor={`case-zoho-id-${caseItem.id}`} style={{ display: 'block', maxWidth: 320 }}>
        Zoho ID
        <input
          id={`case-zoho-id-${caseItem.id}`}
          className="admin-input"
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setSaved(false)
          }}
          placeholder="INS-697"
          maxLength={64}
          readOnly={!canEdit}
          disabled={!canEdit}
        />
      </label>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.85rem' }}>{error}</p> : null}
      {saved ? <p className="admin-muted" style={{ fontSize: '0.85rem' }}>Zoho ID saved.</p> : null}
      {canEdit ? (
        <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={saving} style={{ marginTop: 8 }}>
          {saving ? 'Saving…' : 'Save Zoho ID'}
        </button>
      ) : null}
    </form>
  )
}
