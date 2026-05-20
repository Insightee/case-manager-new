import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import { AddressFormFields, addressFromApi, addressToPayload, emptyAddress } from '../shared/AddressFormFields.jsx'
import { AvatarUpload } from '../shared/AvatarUpload.jsx'
import { TherapistServiceProfileSection } from './TherapistServiceProfileSection.jsx'
import { TherapistReviewsSection } from './TherapistReviewsSection.jsx'
import './therapist-profile.css'

const STATUS_COLORS = {
  ACTIVE: { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  SUSPENDED: { bg: '#fefce8', color: '#a16207', border: '#fde047' },
  ARCHIVED: { bg: '#f4f4f5', color: '#71717a', border: '#d4d4d8' },
}

const STATUS_OPTIONS = ['ACTIVE', 'SUSPENDED']

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

function ProfileField({ label, value, emptyText = 'Not set' }) {
  return (
    <div className="therapist-profile__field">
      <span className="therapist-profile__field-label">{label}</span>
      <span className={`therapist-profile__field-value ${!value ? 'therapist-profile__field-value--empty' : ''}`}>
        {value || emptyText}
      </span>
    </div>
  )
}

export function TherapistProfilePage() {
  const { user, reload } = useAuth()
  const [editingAccount, setEditingAccount] = useState(false)
  const [form, setForm] = useState({ full_name: '', phone: '', employment_status: 'ACTIVE' })
  const [home, setHome] = useState(emptyAddress())
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (user) {
      setForm({
        full_name: user.full_name || '',
        phone: user.phone || '',
        employment_status: user.employment_status || 'ACTIVE',
      })
      setHome(addressFromApi(user.home_address))
    }
  }, [user])

  function cancelEdit() {
    setEditingAccount(false)
    setError('')
    if (user) {
      setForm({
        full_name: user.full_name || '',
        phone: user.phone || '',
        employment_status: user.employment_status || 'ACTIVE',
      })
      setHome(addressFromApi(user.home_address))
    }
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch('/api/v1/auth/me', {
        method: 'PATCH',
        body: JSON.stringify({
          full_name: form.full_name || null,
          phone: form.phone?.trim() || null,
          employment_status: form.employment_status,
          ...homePayload(home),
        }),
      })
      await reload()
      setSuccess('Profile updated.')
      setEditingAccount(false)
    } catch (err) {
      setError(err.message || 'Could not update profile')
    } finally {
      setSaving(false)
    }
  }

  const statusStyle = STATUS_COLORS[form.employment_status] || STATUS_COLORS.ACTIVE
  const homeSummary = [user?.home_address?.city, user?.home_address?.state].filter(Boolean).join(', ')

  return (
    <div className="therapist-profile">
      <header>
        <p className="therapist-profile__eyebrow">My account</p>
        <h1 className="therapist-profile__title">Profile</h1>
        <p className="therapist-profile__intro">
          Your admin may have added contact details when you joined. Review everything below — this layout is ready
          for a future public therapist page families can browse.
        </p>
      </header>

      {error ? <p className="therapist-profile__alert therapist-profile__alert--error">{error}</p> : null}
      {success ? <p className="therapist-profile__alert therapist-profile__alert--success">{success}</p> : null}

      <section className="therapist-profile__hero">
        <AvatarUpload user={user} onUpdated={reload} size={80} />
        <div className="therapist-profile__hero-main">
          <h2 className="therapist-profile__hero-name">{user?.full_name || 'Therapist'}</h2>
          <p className="therapist-profile__hero-meta">{user?.email}</p>
          {user?.phone ? <p className="therapist-profile__hero-meta">{user.phone}</p> : null}
          <span
            style={{
              display: 'inline-block',
              marginTop: 10,
              fontSize: '0.72rem',
              fontWeight: 600,
              padding: '3px 10px',
              borderRadius: 20,
              background: statusStyle.bg,
              color: statusStyle.color,
              border: `1px solid ${statusStyle.border}`,
            }}
          >
            {form.employment_status}
          </span>
        </div>
      </section>

      <section className="therapist-profile__card">
        <div className="therapist-profile__card-head">
          <h2>Contact & account</h2>
          {!editingAccount ? (
            <button type="button" className="therapist-profile__edit-btn" onClick={() => setEditingAccount(true)}>
              Edit
            </button>
          ) : null}
        </div>
        <p className="therapist-profile__card-hint">Login email is managed by your organization — contact admin to change it.</p>

        {!editingAccount ? (
          <div className="therapist-profile__fields">
            <ProfileField label="Email" value={user?.email} />
            <ProfileField label="Full name" value={user?.full_name} />
            <ProfileField label="Phone" value={user?.phone} emptyText="Add a phone number for scheduling" />
            <ProfileField
              label="Home / base address"
              value={
                user?.home_address?.address_line1
                  ? `${user.home_address.address_line1}${homeSummary ? ` · ${homeSummary}` : ''}`
                  : null
              }
              emptyText="Add your base location for homecare planning"
            />
          </div>
        ) : (
          <form className="therapist-profile__form" onSubmit={handleSave}>
            <label>
              Email (read-only)
              <input type="email" value={user?.email || ''} disabled />
            </label>
            <label>
              Full name
              <input
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </label>
            <label>
              Phone
              <input
                type="tel"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="Contact number for scheduling"
              />
            </label>
            <div>
              <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Home / base address</p>
              <AddressFormFields value={home} onChange={setHome} idPrefix="home" disabled={saving} />
            </div>
            <div>
              <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Availability status</p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
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
            </div>
            <div className="therapist-profile__form-actions">
              <button type="submit" className="therapist-profile__save" disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
              <button type="button" className="therapist-profile__cancel" onClick={cancelEdit} disabled={saving}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </section>

      <TherapistServiceProfileSection />

      <section className="therapist-profile__card">
        <h2 style={{ margin: '0 0 12px', fontSize: '1rem', fontWeight: 600 }}>Assigned services</h2>
        <div className="therapist-profile__chips">
          {user?.module_assignments?.length ? (
            user.module_assignments.map((m) => (
              <span key={m} className="therapist-profile__chip">
                {m.replace(/_/g, ' ')}
              </span>
            ))
          ) : (
            <span className="therapist-profile__reviews-empty">No service modules assigned</span>
          )}
        </div>
      </section>

      <TherapistReviewsSection />
    </div>
  )
}
