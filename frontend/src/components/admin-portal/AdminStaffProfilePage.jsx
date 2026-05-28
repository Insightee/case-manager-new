import { useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AvatarUpload } from '../shared/AvatarUpload.jsx'
import { AdminPageHeader, AdminPanel } from './ui/index.js'

function initialForm(user) {
  return {
    bio: user?.bio || '',
    job_title: user?.job_title || '',
    department: user?.department || '',
    timezone: user?.timezone || '',
    ui_compact_mode: Boolean(user?.ui_preferences?.compact_mode),
    ui_dense_tables: Boolean(user?.ui_preferences?.dense_tables),
    notify_email: user?.notification_preferences?.email !== false,
    notify_push: Boolean(user?.notification_preferences?.push),
  }
}

export function AdminStaffProfilePage() {
  const { user, reload } = useAuth()
  const [form, setForm] = useState(() => initialForm(user))
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const staffIdentity = useMemo(
    () => ({
      name: user?.full_name || '—',
      email: user?.email || '—',
      phone: user?.phone || '—',
      staffId: user?.staff_id || '—',
    }),
    [user],
  )

  async function saveProfile(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')
    try {
      await apiFetch('/api/v1/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({
          bio: form.bio,
          job_title: form.job_title,
          department: form.department,
          timezone: form.timezone,
          ui_preferences: {
            compact_mode: form.ui_compact_mode,
            dense_tables: form.ui_dense_tables,
          },
          notification_preferences: {
            email: form.notify_email,
            push: form.notify_push,
          },
        }),
      })
      await reload()
      setMessage('Profile updated.')
    } catch (err) {
      setError(err.message || 'Could not update profile')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Account"
        title="My staff profile"
        subtitle="Update your profile details and preferences. Identity fields are locked."
      />

      <AdminPanel title="Profile photo">
        <AvatarUpload user={user} onUpdated={reload} />
      </AdminPanel>

      <AdminPanel title="Identity (read-only)">
        <div className="admin-form-grid">
          <label>
            Name
            <input className="admin-input" value={staffIdentity.name} readOnly disabled />
          </label>
          <label>
            Email
            <input className="admin-input" value={staffIdentity.email} readOnly disabled />
          </label>
          <label>
            Phone
            <input className="admin-input" value={staffIdentity.phone} readOnly disabled />
          </label>
          <label>
            Staff ID
            <input className="admin-input" value={staffIdentity.staffId} readOnly disabled />
          </label>
        </div>
      </AdminPanel>

      <AdminPanel title="About you">
        <form onSubmit={saveProfile} className="admin-form-grid">
          <label>
            Job title
            <input
              className="admin-input"
              value={form.job_title}
              onChange={(e) => setForm((f) => ({ ...f, job_title: e.target.value }))}
              placeholder="Case Manager"
            />
          </label>
          <label>
            Department
            <input
              className="admin-input"
              value={form.department}
              onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
              placeholder="Operations"
            />
          </label>
          <label>
            Timezone
            <input
              className="admin-input"
              value={form.timezone}
              onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
              placeholder="Asia/Kolkata"
            />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Bio
            <textarea
              className="admin-input"
              rows={4}
              value={form.bio}
              onChange={(e) => setForm((f) => ({ ...f, bio: e.target.value }))}
              placeholder="Tell your team about your background and focus areas."
            />
          </label>

          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={form.ui_compact_mode}
              onChange={(e) => setForm((f) => ({ ...f, ui_compact_mode: e.target.checked }))}
            />
            Compact mode
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={form.ui_dense_tables}
              onChange={(e) => setForm((f) => ({ ...f, ui_dense_tables: e.target.checked }))}
            />
            Dense tables
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={form.notify_email}
              onChange={(e) => setForm((f) => ({ ...f, notify_email: e.target.checked }))}
            />
            Email notifications
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={form.notify_push}
              onChange={(e) => setForm((f) => ({ ...f, notify_push: e.target.checked }))}
            />
            Push notifications
          </label>

          <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={saving}>
              {saving ? 'Saving…' : 'Save profile'}
            </button>
          </div>
        </form>
        {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
        {message ? <p className="admin-alert admin-alert--success">{message}</p> : null}
      </AdminPanel>
    </div>
  )
}
