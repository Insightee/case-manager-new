import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'

export function ParentChangePasswordSection() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPasswords, setShowPasswords] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (newPassword.length < 6) {
      setError('New password needs at least 6 characters.')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.')
      return
    }
    setBusy(true)
    try {
      await apiFetch('/api/v1/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setSuccess('Password updated. Use your new password next time you sign in.')
    } catch (err) {
      setError(err.message || 'Could not update password')
    } finally {
      setBusy(false)
    }
  }

  const inputType = showPasswords ? 'text' : 'password'

  return (
    <section className="parent-profile__card parent-profile__password">
      <h3>Password</h3>
      <p className="parent-profile__hint">
        Update your sign-in password here. Forgot it?{' '}
        <Link to="/clientlogin" state={{ forgotPassword: true }}>
          Reset from the login page
        </Link>
        .
      </p>
      <form className="parent-profile__password-form" onSubmit={handleSubmit}>
        <label className="parent-profile__field">
          Current password
          <input
            type={inputType}
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <label className="parent-profile__field">
          New password
          <input
            type={inputType}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <label className="parent-profile__field">
          Confirm new password
          <input
            type={inputType}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </label>
        <div className="parent-profile__password-actions">
          <button type="button" className="parent-profile__password-toggle" onClick={() => setShowPasswords((v) => !v)}>
            {showPasswords ? 'Hide passwords' : 'Show passwords'}
          </button>
          <button type="submit" className="parent-profile__password-save" disabled={busy}>
            {busy ? 'Updating…' : 'Update password'}
          </button>
        </div>
      </form>
      {error ? <p className="parent-profile__alert parent-profile__alert--error">{error}</p> : null}
      {success ? <p className="parent-profile__alert parent-profile__alert--success">{success}</p> : null}
    </section>
  )
}
