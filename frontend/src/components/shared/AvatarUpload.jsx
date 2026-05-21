import { useEffect, useRef, useState } from 'react'
import { apiFetch, apiFetchBlob, apiUpload } from '../../lib/apiClient.js'

const MAX_BYTES = 1_048_576
const ALLOWED = ['image/jpeg', 'image/png', 'image/webp']

/** @deprecated Use AuthenticatedAvatar — plain URLs require auth and break in <img>. */
export function avatarSrc(user) {
  if (!user?.avatar_url) return null
  return null
}

function useAuthenticatedAvatarSrc(user) {
  const [blobUrl, setBlobUrl] = useState(null)

  useEffect(() => {
    if (!user?.avatar_url) {
      setBlobUrl(null)
      return undefined
    }

    let revoked = null
    let cancelled = false

    apiFetchBlob(`${user.avatar_url.split('?')[0]}?t=${Date.now()}`)
      .then((blob) => {
        if (cancelled) return
        revoked = URL.createObjectURL(blob)
        setBlobUrl(revoked)
      })
      .catch(() => {
        if (!cancelled) setBlobUrl(null)
      })

    return () => {
      cancelled = true
      if (revoked) URL.revokeObjectURL(revoked)
    }
  }, [user?.avatar_url, user?.id])

  return blobUrl
}

/** Avatar image that loads via authenticated fetch (API requires Bearer token). */
export function AuthenticatedAvatar({ user, className, style, size = 48 }) {
  const src = useAuthenticatedAvatarSrc(user)
  const initial = user?.full_name?.charAt(0)?.toUpperCase() || '?'

  return (
    <div
      className={className}
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
        ...style,
      }}
    >
      {src ? (
        <img src={src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      ) : (
        initial
      )}
    </div>
  )
}

export function AvatarUpload({ user, onUpdated, size = 80 }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const previewSrc = useAuthenticatedAvatarSrc(user)

  async function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setError('')
    if (!ALLOWED.includes(file.type) && !/\.(jpe?g|png|webp)$/i.test(file.name)) {
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

  return (
    <div className="avatar-upload">
      <div className="avatar-upload__row">
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
          {previewSrc ? (
            <img src={previewSrc} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            user?.full_name?.charAt(0).toUpperCase() || '?'
          )}
        </div>
        <div className="avatar-upload__actions">
          <button
            type="button"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
            className="avatar-upload__btn"
          >
            {uploading ? 'Uploading…' : 'Upload photo'}
          </button>
          {user?.avatar_url ? (
            <button
              type="button"
              disabled={uploading}
              onClick={handleRemove}
              className="avatar-upload__btn avatar-upload__btn--danger"
            >
              Remove
            </button>
          ) : null}
        </div>
      </div>
      <p className="avatar-upload__hint">JPEG, PNG, or WebP. Max 1 MB.</p>
      {error ? <p className="avatar-upload__error">{error}</p> : null}
      <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" hidden onChange={handleFile} />
    </div>
  )
}
