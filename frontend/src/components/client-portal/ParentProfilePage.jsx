import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { AvatarUpload } from '../shared/AvatarUpload.jsx'

export function ParentProfilePage() {
  const { user, reload } = useAuth()
  const [fullName, setFullName] = useState('')
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (user) setFullName(user.full_name || '')
  }, [user])

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch('/api/v1/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({ full_name: fullName }),
      })
      await reload()
      setSuccess('Profile updated.')
    } catch (err) {
      setError(err.message || 'Could not update profile')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: 20 }}>
        Personalise your family portal with a photo and display name.
      </p>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      {success ? <p style={{ color: '#15803d', fontSize: '0.875rem' }}>{success}</p> : null}
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24 }}>
        <AvatarUpload user={user} onUpdated={reload} size={72} />
        <form onSubmit={handleSave} style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 500 }}>
            Display name
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db' }}
            />
          </label>
          <p style={{ fontSize: '0.8rem', color: '#9ca3af', margin: 0 }}>{user?.email}</p>
          <button
            type="submit"
            disabled={saving}
            style={{
              padding: '10px',
              borderRadius: 8,
              background: '#6366f1',
              color: '#fff',
              fontWeight: 600,
              border: 'none',
              cursor: saving ? 'not-allowed' : 'pointer',
            }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </form>
      </div>
    </div>
  )
}
