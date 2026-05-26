import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'

export function ResetPasswordPage() {
  const { token } = useParams()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const [preview, setPreview] = useState(null)
  const [previewError, setPreviewError] = useState('')

  useEffect(() => {
    if (!token) return
    apiFetch(`/api/v1/auth/reset-password/${token}/preview`)
      .then((data) => setPreview(data))
      .catch((err) => setPreviewError(err.message || 'Reset link is invalid or expired'))
  }, [token])

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
      await apiFetch('/api/v1/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, password }),
      })
      setDone(true)
    } catch (err) {
      setError(err.message || 'Could not reset password')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-card is-signin">
        <div className="login-main">
          <p className="login-brand">InsightCase</p>
          <h1>Choose a new password</h1>
          {preview?.email ? (
            <p className="login-sub" style={{ fontSize: '0.85rem' }}>
              Account: <strong>{preview.email}</strong>
            </p>
          ) : null}
          {previewError ? <p className="login-error">{previewError}</p> : null}

          {done ? (
            <>
              <p className="login-sub" role="status">
                Your password has been updated. You can sign in with your new password.
              </p>
              <p className="login-sub" style={{ marginTop: '1.25rem' }}>
                <Link to="/login">Sign in</Link>
              </p>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="login-form">
              <label>
                New password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                  required
                  disabled={!!previewError}
                />
              </label>
              <label>
                Confirm password
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                  minLength={6}
                  required
                  disabled={!!previewError}
                />
              </label>
              {error ? (
                <p className="login-error" role="alert">
                  {error}
                </p>
              ) : null}
              <button
                type="submit"
                className="login-submit"
                disabled={submitting || !!previewError}
              >
                {submitting ? 'Saving…' : 'Update password'}
              </button>
            </form>
          )}

          {!done ? (
            <p className="login-sub" style={{ marginTop: '1.25rem' }}>
              <Link to="/login">Back to sign in</Link>
            </p>
          ) : null}
        </div>
      </section>
    </div>
  )
}
