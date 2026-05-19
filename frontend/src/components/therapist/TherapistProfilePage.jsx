import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { AddressFormFields, addressFromApi, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'
import { AvatarUpload } from '../shared/AvatarUpload.jsx'
import { TherapistServiceProfileSection } from './TherapistServiceProfileSection.jsx'

const STATUS_OPTIONS = ['ACTIVE', 'SUSPENDED']

const STATUS_COLORS = {
  ACTIVE: { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  SUSPENDED: { bg: '#fefce8', color: '#a16207', border: '#fde047' },
  ARCHIVED: { bg: '#f4f4f5', color: '#71717a', border: '#d4d4d8' },
}

function homePayload(addr) {
  const base = addressToPayload(addr)
  return {
    home_address_line1: base.address_line1,
    home_address_line2: base.address_line2,
    home_city: base.city,
    home_state: base.state,
    home_pincode: base.pincode,
    home_landmark: base.landmark,
    home_latitude: base.latitude,
    home_longitude: base.longitude,
  }
}

export function TherapistProfilePage() {
  const { user, reload } = useAuth()
  const [form, setForm] = useState({ full_name: '', employment_status: 'ACTIVE' })
  const [home, setHome] = useState(emptyAddress())
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (user) {
      setForm({
        full_name: user.full_name || '',
        employment_status: user.employment_status || 'ACTIVE',
      })
      setHome(addressFromApi(user.home_address))
    }
  }, [user])

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const body = {
        full_name: form.full_name || null,
        employment_status: form.employment_status,
        ...homePayload(home),
      }
      await apiFetch('/api/v1/auth/me', { method: 'PATCH', body: JSON.stringify(body) })
      await reload()
      setSuccess('Profile updated successfully.')
    } catch (err) {
      setError(err.message || 'Could not update profile')
    } finally {
      setSaving(false)
    }
  }

  const statusStyle = STATUS_COLORS[form.employment_status] || STATUS_COLORS.ACTIVE

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 28 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
          My account
        </p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Profile</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>
          Update your personal details, home base address, and availability.
        </p>
      </header>

      {error ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>
          {error}
        </div>
      ) : null}
      {success ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#15803d', fontSize: '0.875rem' }}>
          {success}
        </div>
      ) : null}

      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '24px 24px', marginBottom: 20 }}>
        <div style={{ marginBottom: 24 }}>
          <AvatarUpload user={user} onUpdated={reload} size={64} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: 16, flexWrap: 'wrap' }}>
          <div>
            <p style={{ fontWeight: 600, margin: 0 }}>{user?.full_name}</p>
            <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: 0 }}>{user?.email}</p>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '3px 10px', borderRadius: 20, background: statusStyle.bg, color: statusStyle.color, border: `1px solid ${statusStyle.border}` }}>
              {form.employment_status}
            </span>
            </div>
          </div>
        </div>

        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
            Full name
            <input
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
              required
            />
          </label>

          <div>
            <p style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: 4 }}>Home / base address</p>
            <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: 0, marginBottom: 12 }}>
              Used as your base location for homecare planning. Map routing coming soon.
            </p>
            <AddressFormFields value={home} onChange={setHome} idPrefix="home" disabled={saving} />
          </div>

          <div>
            <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Availability status</p>
            <div style={{ display: 'flex', gap: 8 }}>
              {STATUS_OPTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setForm({ ...form, employment_status: s })}
                  style={{
                    padding: '6px 16px',
                    borderRadius: 20,
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: form.employment_status === s ? `2px solid ${STATUS_COLORS[s].color}` : '1px solid #d1d5db',
                    background: form.employment_status === s ? STATUS_COLORS[s].bg : '#fff',
                    color: form.employment_status === s ? STATUS_COLORS[s].color : '#374151',
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
            <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: 6 }}>
              To archive your account, please contact HR or an admin.
            </p>
          </div>

          <button
            type="submit"
            disabled={saving}
            style={{ padding: '10px', borderRadius: 8, background: '#6366f1', color: '#fff', fontWeight: 600, fontSize: '0.875rem', border: 'none', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1, marginTop: 4 }}
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </div>

      <TherapistServiceProfileSection />

      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '20px 24px' }}>
        <p style={{ fontWeight: 600, marginBottom: 12 }}>Assigned services</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {user?.module_assignments?.length ? (
            user.module_assignments.map((m) => (
              <span key={m} style={{ background: '#eef2ff', color: '#3730a3', fontSize: '0.75rem', fontWeight: 600, padding: '4px 12px', borderRadius: 20, textTransform: 'capitalize' }}>
                {m.replace(/_/g, ' ')}
              </span>
            ))
          ) : (
            <span style={{ color: '#9ca3af', fontSize: '0.875rem' }}>No service modules assigned</span>
          )}
        </div>
        <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: 8 }}>
          Platform modules assigned by admin. Your public service profile lists what you offer to families.
        </p>
      </div>
    </div>
  )
}
