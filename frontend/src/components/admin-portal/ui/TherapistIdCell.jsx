import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

function readTherapistId(user) {
  if (!user) return ''
  return String(user.external_employee_id || user.staff_id || '').trim()
}

export function TherapistIdCell({ user, canEdit, onSaved, onError, onReload }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(() => readTherapistId(user))
  const [displayId, setDisplayId] = useState(() => readTherapistId(user))
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const next = readTherapistId(user)
    setDisplayId(next)
    if (!editing) setValue(next)
  }, [user?.id, user?.external_employee_id, user?.staff_id, editing])

  const display = displayId || '—'

  async function save(nextValue) {
    if (!user?.id || !canEdit) return
    const trimmed = nextValue.trim()
    setSaving(true)
    onError?.('')
    try {
      let updated = await apiFetch(`/api/v1/admin/users/${user.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ external_employee_id: trimmed || null }),
      })
      let saved = readTherapistId(updated)
      if (!saved && trimmed) {
        updated = await apiFetch(`/api/v1/admin/users/${user.id}`)
        saved = readTherapistId(updated)
      }
      if (trimmed && !saved) {
        throw new Error('Therapist ID was not saved. Restart the API server and try again.')
      }
      setDisplayId(saved)
      setValue(saved)
      setEditing(false)
      onSaved?.(updated)
      await onReload?.()
    } catch (err) {
      onError?.(err.message || 'Could not update therapist ID')
    } finally {
      setSaving(false)
    }
  }

  if (!canEdit) {
    return <span className="admin-muted">{display}</span>
  }

  if (editing) {
    return (
      <form
        className="admin-btn-group admin-btn-group--wrap"
        onSubmit={(e) => {
          e.preventDefault()
          e.stopPropagation()
          save(value)
        }}
      >
        <input
          className="admin-input admin-input--sm"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Therapist ID"
          maxLength={64}
          disabled={saving}
          autoFocus
          style={{ minWidth: 88, maxWidth: 140 }}
        />
        <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={saving}>
          {saving ? '…' : 'Save'}
        </button>
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          disabled={saving}
          onClick={() => {
            setValue(displayId)
            setEditing(false)
          }}
        >
          Cancel
        </button>
      </form>
    )
  }

  return (
    <span className="admin-btn-group admin-btn-group--wrap" style={{ alignItems: 'center' }}>
      <span className={display === '—' ? 'admin-muted' : undefined}>{display}</span>
      <button
        type="button"
        className="admin-btn admin-btn--ghost admin-btn--sm"
        onClick={() => {
          setValue(displayId)
          setEditing(true)
        }}
        aria-label={`Edit therapist ID for ${user?.full_name || user?.email || 'user'}`}
      >
        Edit
      </button>
    </span>
  )
}
