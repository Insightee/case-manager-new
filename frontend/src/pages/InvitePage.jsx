import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || ''

export function InvitePage() {
  const { token } = useParams()
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const res = await fetch(`${API_URL}/api/v1/auth/accept-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, full_name: fullName, password }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || 'Invite failed')
      }
      setMessage('Account created. You can sign in now.')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="login-shell">
      <section className="login-card is-signin">
        <div className="login-main">
          <p className="login-brand">InsightCase</p>
          <h1>Accept invitation</h1>
          <p className="login-sub">Set your password to join as a therapist.</p>
          {message ? (
            <p className="login-hint">
              {message} <Link to="/login">Sign in</Link>
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="login-form">
              <label>
                Full name
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
              </label>
              <label>
                Password
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
              </label>
              {error ? <p className="login-error">{error}</p> : null}
              <button type="submit" className="login-submit">
                Create account
              </button>
            </form>
          )}
        </div>
      </section>
    </div>
  )
}
