import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'
import { setTokens } from '../lib/apiClient.js'
import { useAuth } from '../context/AuthContext.jsx'

const API_URL = import.meta.env.VITE_API_URL || ''

const ROLE_LABELS = {
  PARENT: { sub: 'Set your password to activate your family account.', cta: 'Activate account' },
  THERAPIST: { sub: 'Set your password to join as a therapist.', cta: 'Create account' },
  HR: { sub: 'Set your password to access the HR portal.', cta: 'Create account' },
  ADMIN: { sub: 'Set your password to access the admin portal.', cta: 'Create account' },
  default: { sub: 'Set your password to complete registration.', cta: 'Create account' },
}

export function InvitePage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { reload } = useAuth()

  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const [roleHint, setRoleHint] = useState(null)
  const [preview, setPreview] = useState(null)
  const [previewError, setPreviewError] = useState('')

  useEffect(() => {
    if (!token) return
    apiFetch(`/api/v1/auth/invite/${token}/preview`)
      .then((data) => {
        setPreview(data)
        if (data.role === 'PARENT') setRoleHint('PARENT')
        else if (data.role) setRoleHint(data.role)
      })
      .catch((err) => setPreviewError(err.message || 'Invite link is invalid or expired'))
  }, [token])

  const copy = ROLE_LABELS[roleHint] || ROLE_LABELS.default

  async function handleSubmit(e) {
    e.preventDefault()
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/accept-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, full_name: fullName.trim(), password }),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) {
        // "User already exists" → prompt to sign in
        if (body.detail?.toLowerCase().includes('already exists')) {
          setError('An account with this email already exists. Please sign in instead.')
          return
        }
        throw new Error(body.detail || 'Could not activate account')
      }
      // Store tokens and reload auth — then navigate to the right portal
      setTokens(body.access_token, body.refresh_token)
      await reload()
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-card is-signin">
        <div className="login-main">
          <p className="login-brand">InsightCase</p>
          <h1>Welcome — activate your account</h1>
          <p className="login-sub">
            {preview?.roleLabel || copy.sub}
            {preview?.childName ? ` for ${preview.childName}` : ''}
          </p>
          {previewError ? <p className="login-error">{previewError}</p> : null}
          {preview?.email ? (
            <p className="login-sub" style={{ fontSize: '0.85rem' }}>
              Signing in as <strong>{preview.email}</strong>
            </p>
          ) : null}

          <form onSubmit={handleSubmit} className="login-form">
            <label>
              Your full name
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="e.g. Priya Sharma"
                required
                autoComplete="name"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
                autoComplete="new-password"
                placeholder="At least 6 characters"
              />
            </label>
            <label>
              Confirm password
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                minLength={6}
                required
                autoComplete="new-password"
                placeholder="Re-enter your password"
              />
            </label>
            {error ? <p className="login-error">{error}</p> : null}
            <button type="submit" className="login-submit" disabled={submitting}>
              {submitting ? 'Activating…' : copy.cta}
            </button>
          </form>

          <p style={{ marginTop: 16, fontSize: '0.8rem', color: '#94a3b8', textAlign: 'center' }}>
            Already have an account?{' '}
            <a href="/login" style={{ color: '#6366f1', fontWeight: 600 }}>
              Sign in
            </a>
          </p>
        </div>
      </section>
    </div>
  )
}
