import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'

const SUCCESS_MESSAGE =
  'If an account exists for that email, you will receive password reset instructions shortly.'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await apiFetch('/api/v1/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim() }),
      })
      setSent(true)
    } catch (err) {
      setError(err.message || 'Could not send reset email')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-card is-signin">
        <div className="login-main">
          <p className="login-brand">InsightCase</p>
          <h1>Reset your password</h1>
          <p className="login-sub">Enter your account email and we will send a reset link.</p>

          {sent ? (
            <p className="login-sub" role="status">
              {SUCCESS_MESSAGE}
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="login-form">
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </label>
              {error ? (
                <p className="login-error" role="alert">
                  {error}
                </p>
              ) : null}
              <button type="submit" className="login-submit" disabled={submitting}>
                {submitting ? 'Sending…' : 'Send reset link'}
              </button>
            </form>
          )}

          <p className="login-sub" style={{ marginTop: '1.25rem' }}>
            <Link to="/login">Back to sign in</Link>
          </p>
        </div>
      </section>
    </div>
  )
}
