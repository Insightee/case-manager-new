import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'

const PROFILE_STATUS = {
  DRAFT: { bg: '#f4f4f5', color: '#52525b', label: 'Draft' },
  PENDING: { bg: '#fef3c7', color: '#b45309', label: 'Pending approval' },
  APPROVED: { bg: '#f0fdf4', color: '#15803d', label: 'Approved' },
  PAUSED: { bg: '#fef2f2', color: '#b91c1c', label: 'Paused by admin' },
}

function serviceLabels(categories, ids) {
  const map = Object.fromEntries((categories || []).map((c) => [c.id, c.label]))
  return (ids || []).map((id) => map[id] || id.replace(/_/g, ' '))
}

export function TherapistServiceProfileSection() {
  const [editing, setEditing] = useState(false)
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
      setEditing(false)
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

  const serviceNames = serviceLabels(categories, form.services_offered)

  return (
    <section className="therapist-profile__card">
      <div className="therapist-profile__card-head">
        <div>
          <h2>Service profile</h2>
          <p className="therapist-profile__card-hint" style={{ marginTop: 4, marginBottom: 0 }}>
            Public-facing listing for families — admin approves before it goes live.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
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
          {!editing && !paused ? (
            <button type="button" className="therapist-profile__edit-btn" onClick={() => setEditing(true)}>
              Edit
            </button>
          ) : null}
        </div>
      </div>

      {profile?.admin_note ? (
        <p style={{ fontSize: '0.8rem', color: '#b45309', marginBottom: 12, padding: '8px 12px', background: '#fffbeb', borderRadius: 8 }}>
          Admin note: {profile.admin_note}
        </p>
      ) : null}

      {!editing ? (
        <div className="therapist-profile__fields">
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Contact email</span>
            <span className="therapist-profile__field-value">{profile?.email || '—'}</span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Display name</span>
            <span className="therapist-profile__field-value">{form.display_name || '—'}</span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Bio</span>
            <span className={`therapist-profile__field-value ${!form.short_bio ? 'therapist-profile__field-value--empty' : ''}`}>
              {form.short_bio || 'Add a short bio'}
            </span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Qualifications</span>
            <span
              className={`therapist-profile__field-value ${!form.academic_qualifications ? 'therapist-profile__field-value--empty' : ''}`}
            >
              {form.academic_qualifications || 'Not added'}
            </span>
          </div>
          {(form.professional_certificates || '').trim() ? (
            <div className="therapist-profile__field">
              <span className="therapist-profile__field-label">Certificates</span>
              <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: '0.875rem' }}>
                {form.professional_certificates.split('\n').filter(Boolean).map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Services</span>
            {serviceNames.length ? (
              <div className="therapist-profile__chips" style={{ marginTop: 6 }}>
                {serviceNames.map((s) => (
                  <span key={s} className="therapist-profile__chip">
                    {s}
                  </span>
                ))}
              </div>
            ) : (
              <span className="therapist-profile__field-value therapist-profile__field-value--empty">Select services</span>
            )}
          </div>
        </div>
      ) : (
      <form onSubmit={saveDraft} className="therapist-profile__form" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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

        <div className="therapist-profile__form-actions">
          <button type="submit" className="therapist-profile__save" disabled={saving || paused}>
            {saving ? 'Saving…' : 'Save draft'}
          </button>
          <button
            type="button"
            className="therapist-profile__cancel"
            disabled={saving}
            onClick={() => {
              setEditing(false)
              setError('')
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            className="therapist-profile__edit-btn"
            disabled={saving || paused || profile?.status === 'PENDING'}
            onClick={submitForApproval}
          >
            Submit for approval
          </button>
        </div>
      </form>
      )}

      {error ? <p className="therapist-profile__alert therapist-profile__alert--error" style={{ marginTop: 12 }}>{error}</p> : null}
      {success ? <p className="therapist-profile__alert therapist-profile__alert--success" style={{ marginTop: 12 }}>{success}</p> : null}
    </section>
  )
}
