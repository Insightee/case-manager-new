import { useRef, useState } from 'react'
import { apiUpload, apiFetch } from '../../lib/apiClient.js'

const MAX_BYTES = 1_048_576
const ALLOWED = ['image/jpeg', 'image/png', 'image/webp']

export function avatarSrc(user) {
  if (!user?.avatar_url) return null
  const base = import.meta.env.VITE_API_URL || ''
  return `${base}${user.avatar_url}?t=${Date.now()}`
}

export function AvatarUpload({ user, onUpdated, size = 48 }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  async function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    if (!ALLOWED.includes(file.type)) {
      setError('Use JPEG, PNG, or WebP.')
      return
    }
    if (file.size > MAX_BYTES) {
      setError('Image must be under 1 MB.')
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      await apiUpload('/api/v1/auth/me/avatar', fd)
      if (onUpdated) await onUpdated()
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  async function handleRemove() {
    setUploading(true)
    setError('')
    try {
      await apiFetch('/api/v1/auth/me/avatar', { method: 'DELETE' })
      if (onUpdated) await onUpdated()
    } catch (err) {
      setError(err.message || 'Could not remove photo')
    } finally {
      setUploading(false)
    }
  }

  const src = avatarSrc(user)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: size,
            height: size,
            borderRadius: '50%',
            overflow: 'hidden',
            background: '#6366f1',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: size * 0.35,
            flexShrink: 0,
          }}
        >
          {src ? (
            <img src={src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            user?.full_name?.charAt(0).toUpperCase() || '?'
          )}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <button
            type="button"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              border: '1px solid #d1d5db',
              background: '#fff',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: uploading ? 'not-allowed' : 'pointer',
            }}
          >
            {uploading ? 'Uploading…' : 'Upload photo'}
          </button>
          {src ? (
            <button
              type="button"
              disabled={uploading}
              onClick={handleRemove}
              style={{
                padding: '6px 12px',
                borderRadius: 8,
                border: '1px solid #fca5a5',
                background: '#fff',
                color: '#b91c1c',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: uploading ? 'not-allowed' : 'pointer',
              }}
            >
              Remove
            </button>
          ) : null}
        </div>
        <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={handleFile} />
      </div>
      <p style={{ fontSize: '0.75rem', color: '#9ca3af', margin: 0 }}>JPEG, PNG, or WebP. Max 1 MB.</p>
      {error ? <p style={{ fontSize: '0.75rem', color: '#b91c1c', margin: 0 }}>{error}</p> : null}
    </div>
  )
}
