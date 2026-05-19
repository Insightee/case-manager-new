import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'

const PROFILE_STATUS = {
  DRAFT: { bg: '#f4f4f5', color: '#52525b', label: 'Draft' },
  PENDING: { bg: '#fef3c7', color: '#b45309', label: 'Pending approval' },
  APPROVED: { bg: '#f0fdf4', color: '#15803d', label: 'Approved' },
  PAUSED: { bg: '#fef2f2', color: '#b91c1c', label: 'Paused by admin' },
}

export function TherapistServiceProfileSection() {
  const [categories, setCategories] = useState([])
  const [profile, setProfile] = useState(null)
  const [form, setForm] = useState({
    display_name: '',
    short_bio: '',
    academic_qualifications: '',
    professional_certificates: '',
    services_offered: [],
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    const [cats, prof] = await Promise.all([
      apiFetch('/api/v1/therapist/service-categories'),
      apiFetch('/api/v1/therapist/profile'),
    ])
    setCategories(cats)
    setProfile(prof)
    setForm({
      display_name: prof.display_name || prof.full_name || '',
      short_bio: prof.short_bio || '',
      academic_qualifications: prof.academic_qualifications || '',
      professional_certificates: (prof.professional_certificates || []).join('\n'),
      services_offered: prof.services_offered || [],
    })
  }

  useEffect(() => {
    load().catch(() => setError('Could not load service profile'))
  }, [])

  const paused = profile?.status === 'PAUSED'
  const st = PROFILE_STATUS[profile?.status] || PROFILE_STATUS.DRAFT

  async function persistDraft() {
    const certs = form.professional_certificates
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    const updated = await apiFetch('/api/v1/therapist/profile', {
      method: 'PUT',
      body: JSON.stringify({
        display_name: form.display_name.trim(),
        short_bio: form.short_bio.trim() || null,
        academic_qualifications: form.academic_qualifications.trim() || null,
        professional_certificates: certs,
        services_offered: form.services_offered,
      }),
    })
    setProfile(updated)
    return updated
  }

  async function saveDraft(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await persistDraft()
      setSuccess('Draft saved. Submit when ready for admin review.')
    } catch (err) {
      setError(err.message || 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  async function submitForApproval() {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await persistDraft()
      const updated = await apiFetch('/api/v1/therapist/profile/submit', { method: 'POST' })
      setProfile(updated)
      setSuccess('Submitted for admin approval.')
    } catch (err) {
      setError(err.message || 'Could not submit')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '24px', marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
        <div>
          <p style={{ fontSize: '0.875rem', fontWeight: 600, margin: 0 }}>Service profile</p>
          <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: 4 }}>
            Showcase your qualifications and services. Admin approves before this is visible to families.
          </p>
        </div>
        {profile ? (
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 600,
              padding: '4px 10px',
              borderRadius: 20,
              background: st.bg,
              color: st.color,
              whiteSpace: 'nowrap',
            }}
          >
            {st.label}
          </span>
        ) : null}
      </div>

      {profile?.admin_note ? (
        <p style={{ fontSize: '0.8rem', color: '#b45309', marginBottom: 12, padding: '8px 12px', background: '#fffbeb', borderRadius: 8 }}>
          Admin note: {profile.admin_note}
        </p>
      ) : null}

      <form onSubmit={saveDraft} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
          Display name
          <input
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            disabled={paused}
            required
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
          />
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
          Short bio
          <textarea
            value={form.short_bio}
            onChange={(e) => setForm({ ...form, short_bio: e.target.value })}
            disabled={paused}
            rows={3}
            maxLength={2000}
            placeholder="A few sentences about your approach and experience"
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }}
          />
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
          Academic qualifications
          <textarea
            value={form.academic_qualifications}
            onChange={(e) => setForm({ ...form, academic_qualifications: e.target.value })}
            disabled={paused}
            rows={2}
            placeholder="Degrees, certifications, institutions"
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }}
          />
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
          Professional certificates
          <textarea
            value={form.professional_certificates}
            onChange={(e) => setForm({ ...form, professional_certificates: e.target.value })}
            disabled={paused}
            rows={3}
            placeholder="One per line, e.g. RCI Registered"
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }}
          />
        </label>

        <div>
          <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Services offered</p>
          <ServiceCategoryPicker
            categories={categories}
            value={form.services_offered}
            onChange={(services_offered) => setForm({ ...form, services_offered })}
            disabled={paused}
          />
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 4 }}>
          <button
            type="submit"
            disabled={saving || paused}
            style={{
              padding: '10px 16px',
              borderRadius: 8,
              background: '#6366f1',
              color: '#fff',
              fontWeight: 600,
              fontSize: '0.875rem',
              border: 'none',
              cursor: saving || paused ? 'not-allowed' : 'pointer',
              opacity: saving || paused ? 0.7 : 1,
            }}
          >
            {saving ? 'Saving…' : 'Save draft'}
          </button>
          <button
            type="button"
            disabled={saving || paused || profile?.status === 'PENDING'}
            onClick={submitForApproval}
            style={{
              padding: '10px 16px',
              borderRadius: 8,
              background: '#fff',
              color: '#3730a3',
              fontWeight: 600,
              fontSize: '0.875rem',
              border: '1px solid #c7d2fe',
              cursor: saving || paused || profile?.status === 'PENDING' ? 'not-allowed' : 'pointer',
            }}
          >
            Submit for approval
          </button>
        </div>
      </form>

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem', marginTop: 12 }}>{error}</p> : null}
      {success ? <p style={{ color: '#15803d', fontSize: '0.875rem', marginTop: 12 }}>{success}</p> : null}
    </div>
  )
}
