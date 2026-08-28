import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../lib/apiClient.js'
import {
  readForgotPasswordCooldownRemaining,
  startForgotPasswordCooldown,
} from '../lib/forgotPasswordCooldown.js'
import { loginPathFromApiPortal, portalLoginPath } from '../lib/portalLogin.js'

const SUCCESS_MESSAGE =
  'If an account exists for that email, you will receive password reset instructions shortly.'

export function ForgotPasswordPage() {
  const [searchParams] = useSearchParams()
  const signInPath = useMemo(() => {
    const portal = searchParams.get('portal')
    if (portal === 'parent' || portal === 'therapist' || portal === 'admin') {
      return portalLoginPath(portal)
    }
    if (portal === 'staff') return loginPathFromApiPortal('staff')
    return portalLoginPath('admin')
  }, [searchParams])

  const [email, setEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)
  const [cooldownRemaining, setCooldownRemaining] = useState(() => readForgotPasswordCooldownRemaining())

  useEffect(() => {
    const remaining = readForgotPasswordCooldownRemaining()
    setCooldownRemaining(remaining)
    if (remaining > 0) {
      setSent(true)
    }
  }, [])

  useEffect(() => {
    if (cooldownRemaining <= 0) return undefined
    const timer = window.setInterval(() => {
      setCooldownRemaining(readForgotPasswordCooldownRemaining())
    }, 1000)
    return () => window.clearInterval(timer)
  }, [cooldownRemaining])

  const resendBlocked = cooldownRemaining > 0

  async function handleSubmit(e) {
    e.preventDefault()
    if (resendBlocked) return
    setError('')
    setSubmitting(true)
    try {
      await apiFetch('/api/v1/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim() }),
      })
      startForgotPasswordCooldown()
      setCooldownRemaining(readForgotPasswordCooldownRemaining())
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
          <p className="login-brand">InsighteCase</p>
          <h1>Reset your password</h1>
          <p className="login-sub">Enter your account email and we will send a reset link.</p>

          {sent ? (
            <p className="login-sub" role="status">
              {SUCCESS_MESSAGE}
            </p>
          ) : null}

          {sent && resendBlocked ? (
            <p className="login-sub" role="status" aria-live="polite">
              You can request another link in{' '}
              <strong>{cooldownRemaining}</strong> second{cooldownRemaining === 1 ? '' : 's'}.
            </p>
          ) : null}

          {!sent || !resendBlocked ? (
            <form onSubmit={handleSubmit} className="login-form">
              <label htmlFor="forgot-email">
                Email
                <input
                  id="forgot-email"
                  name="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  disabled={submitting || resendBlocked}
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
                disabled={submitting || resendBlocked}
              >
                {submitting ? 'Sending…' : sent ? 'Send another link' : 'Send reset link'}
              </button>
            </form>
          ) : (
            <button type="button" className="login-submit" disabled aria-disabled="true">
              Send another link in {cooldownRemaining}s
            </button>
          )}

          <p className="login-sub" style={{ marginTop: '1.25rem' }}>
            <Link to={signInPath}>Back to sign in</Link>
          </p>
        </div>
      </section>
    </div>
  )
}
