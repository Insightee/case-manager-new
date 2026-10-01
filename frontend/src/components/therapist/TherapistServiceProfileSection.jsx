import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { QualificationLevelPicker } from '../shared/QualificationLevelPicker.jsx'
import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'
import { qualificationLevelLabel } from '../../lib/therapistQualificationLevels.js'

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

function profileFormFromRecord(prof) {
  const pending = prof?.pending_submission
  const source = pending || prof || {}
  return {
    display_name: source.display_name || prof?.full_name || '',
    short_bio: source.short_bio || '',
    academic_qualifications: source.academic_qualifications || '',
    academic_qualification_level: source.academic_qualification_level || prof?.academic_qualification_level || '',
    professional_certificates: (source.professional_certificates || []).join('\n'),
    services_offered: source.services_offered || [],
    employment_start_date: prof?.employment_start_date || '',
  }
}

function publishedFormFromRecord(prof) {
  return {
    display_name: prof?.display_name || prof?.full_name || '',
    short_bio: prof?.short_bio || '',
    academic_qualifications: prof?.academic_qualifications || '',
    academic_qualification_level: prof?.academic_qualification_level || '',
    professional_certificates: (prof?.professional_certificates || []).join('\n'),
    services_offered: prof?.services_offered || [],
    employment_start_date: prof?.employment_start_date || '',
  }
}

export function TherapistServiceProfileSection({
  onProfileUpdated,
  editRequestKey = null,
  onEditRequestHandled,
  sectionClassName = '',
}) {
  const [editing, setEditing] = useState(false)
  const [categories, setCategories] = useState([])
  const [profile, setProfile] = useState(null)
  const [form, setForm] = useState({
    display_name: '',
    short_bio: '',
    academic_qualifications: '',
    academic_qualification_level: '',
    professional_certificates: '',
    services_offered: [],
    employment_start_date: '',
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
    setForm(publishedFormFromRecord(prof))
  }

  useEffect(() => {
    load().catch(() => setError('Could not load service profile'))
  }, [])

  const paused = profile?.status === 'PAUSED'

  useEffect(() => {
    if (!editRequestKey || !profile || paused) return
    setForm(profileFormFromRecord(profile))
    setEditing(true)
    setError('')
    setSuccess('')
    onEditRequestHandled?.()
  }, [editRequestKey, profile, paused, onEditRequestHandled])
  const awaitingFirstApproval = profile?.status === 'PENDING' && !profile?.approved_snapshot
  const hasPendingChanges = Boolean(profile?.has_pending_changes)
  const statusKey = hasPendingChanges ? 'PENDING' : profile?.status
  const st = PROFILE_STATUS[statusKey] || PROFILE_STATUS.DRAFT

  function openEdit() {
    setForm(profileFormFromRecord(profile))
    setEditing(true)
    setError('')
    setSuccess('')
  }

  function cancelEdit() {
    setForm(publishedFormFromRecord(profile))
    setEditing(false)
    setError('')
  }

  async function submitForApproval(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const certs = form.professional_certificates
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
      const updated = await apiFetch('/api/v1/therapist/profile/submit', {
        method: 'POST',
        body: JSON.stringify({
          display_name: form.display_name.trim(),
          short_bio: form.short_bio.trim() || null,
          academic_qualifications: form.academic_qualifications.trim() || null,
          academic_qualification_level: form.academic_qualification_level || null,
          professional_certificates: certs,
          services_offered: form.services_offered,
          employment_start_date: form.employment_start_date || null,
        }),
      })
      setProfile(updated)
      setForm(publishedFormFromRecord(updated))
      setEditing(false)
      setSuccess(
        updated.has_pending_changes || updated.status === 'PENDING'
          ? 'Submitted for admin approval. Your live listing stays unchanged until approved.'
          : 'Profile updated.',
      )
      await onProfileUpdated?.()
    } catch (err) {
      setError(err.message || 'Could not submit')
    } finally {
      setSaving(false)
    }
  }

  const viewForm = publishedFormFromRecord(profile)
  const serviceNames = serviceLabels(categories, viewForm.services_offered)

  return (
    <section id="therapist-profile-service" className={`therapist-profile__card${sectionClassName}`}>
      <div className="therapist-profile__card-head">
        <div>
          <h2>Service profile</h2>
          <p className="therapist-profile__card-hint" style={{ marginTop: 4, marginBottom: 0 }}>
            Public-facing listing for families — admin approves before updates go live.
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
              {hasPendingChanges ? 'Changes pending approval' : st.label}
            </span>
          ) : null}
          {!editing && !paused && !awaitingFirstApproval ? (
            <button type="button" className="therapist-profile__edit-btn" onClick={openEdit}>
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

      {hasPendingChanges ? (
        <p style={{ fontSize: '0.8rem', color: '#b45309', marginBottom: 12, padding: '8px 12px', background: '#fffbeb', borderRadius: 8 }}>
          You have updates waiting for admin review. Your current listing below is still what families see.
        </p>
      ) : null}

      {!editing ? (
        <div className="therapist-profile__fields">
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Contact email</span>
            <span className="therapist-profile__field-value">{profile?.email || '—'}</span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Start date</span>
            <span className="therapist-profile__field-value">
              {viewForm.employment_start_date
                ? new Date(viewForm.employment_start_date).toLocaleDateString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  })
                : '—'}
            </span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Display name</span>
            <span className="therapist-profile__field-value">{viewForm.display_name || '—'}</span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Bio</span>
            <span className={`therapist-profile__field-value ${!viewForm.short_bio ? 'therapist-profile__field-value--empty' : ''}`}>
              {viewForm.short_bio || 'Add a short bio'}
            </span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Highest qualification</span>
            <span
              className={`therapist-profile__field-value ${!viewForm.academic_qualification_level ? 'therapist-profile__field-value--empty' : ''}`}
            >
              {qualificationLevelLabel(viewForm.academic_qualification_level) || 'Select your highest level'}
            </span>
          </div>
          {viewForm.academic_qualifications ? (
            <div className="therapist-profile__field">
              <span className="therapist-profile__field-label">Additional qualification details</span>
              <span className="therapist-profile__field-value">{viewForm.academic_qualifications}</span>
            </div>
          ) : null}
          {(viewForm.professional_certificates || '').trim() ? (
            <div className="therapist-profile__field">
              <span className="therapist-profile__field-label">Certificates</span>
              <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: '0.875rem' }}>
                {viewForm.professional_certificates.split('\n').filter(Boolean).map((c) => (
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
      <form onSubmit={submitForApproval} className="therapist-profile__form" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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
          Start date
          <input
            type="date"
            value={form.employment_start_date || ''}
            onChange={(e) => setForm({ ...form, employment_start_date: e.target.value || '' })}
            disabled={paused}
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

        <div>
          <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Highest qualification</p>
          <QualificationLevelPicker
            value={form.academic_qualification_level}
            onChange={(academic_qualification_level) => setForm({ ...form, academic_qualification_level })}
            disabled={paused}
          />
        </div>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
          Additional qualification details (optional)
          <textarea
            value={form.academic_qualifications}
            onChange={(e) => setForm({ ...form, academic_qualifications: e.target.value })}
            disabled={paused}
            rows={2}
            placeholder="Degree name, institution, year"
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
          <button type="submit" className="therapist-profile__edit-btn" disabled={saving || paused}>
            {saving ? 'Submitting…' : 'Submit for approval'}
          </button>
          <button
            type="button"
            className="therapist-profile__cancel"
            disabled={saving}
            onClick={cancelEdit}
          >
            Cancel
          </button>
        </div>
      </form>
      )}

      {error ? <p className="therapist-profile__alert therapist-profile__alert--error" style={{ marginTop: 12 }}>{error}</p> : null}
      {success ? <p className="therapist-profile__alert therapist-profile__alert--success" style={{ marginTop: 12 }}>{success}</p> : null}
    </section>
  )
}
