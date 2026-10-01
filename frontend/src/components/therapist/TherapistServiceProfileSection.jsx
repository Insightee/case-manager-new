import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { QualificationLevelPicker } from '../shared/QualificationLevelPicker.jsx'
import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'
import { qualificationLevelLabel } from '../../lib/therapistQualificationLevels.js'
import {
  addQualificationEntry,
  normalizeQualificationEntries,
  removeQualificationEntry,
  submitHelperText,
  wordCount,
} from '../../lib/therapistProfileQuality.js'

const PROFILE_STATUS = {
  DRAFT: { bg: '#f4f4f5', color: '#52525b', label: 'Draft' },
  PENDING: { bg: '#fef3c7', color: '#b45309', label: 'Pending approval' },
  CHANGES_REQUESTED: { bg: '#fff7ed', color: '#c2410c', label: 'Updates requested' },
  APPROVED: { bg: '#f0fdf4', color: '#15803d', label: 'Approved' },
  PAUSED: { bg: '#fef2f2', color: '#b91c1c', label: 'Paused by admin' },
}

function serviceLabels(categories, ids) {
  const map = Object.fromEntries((categories || []).map((c) => [c.id, c.label]))
  return (ids || []).map((id) => map[id] || id.replace(/_/g, ' '))
}

function entriesFromRecord(source, fallback) {
  const raw = source?.professional_qualification_entries
  if (raw?.length) return normalizeQualificationEntries(raw)
  const certs = source?.professional_certificates || fallback?.professional_certificates || []
  return normalizeQualificationEntries(certs)
}

function profileFormFromRecord(prof) {
  const pending = prof?.pending_submission
  const source = pending || prof || {}
  return {
    display_name: source.display_name || prof?.full_name || '',
    short_bio: source.short_bio || '',
    academic_qualification_level: source.academic_qualification_level || prof?.academic_qualification_level || '',
    professional_qualification_entries: entriesFromRecord(source, prof),
    services_offered: source.services_offered || [],
    employment_start_date: prof?.employment_start_date || '',
  }
}

function publishedFormFromRecord(prof) {
  return {
    display_name: prof?.display_name || prof?.full_name || '',
    short_bio: prof?.short_bio || '',
    academic_qualification_level: prof?.academic_qualification_level || '',
    professional_qualification_entries: entriesFromRecord(prof),
    services_offered: prof?.services_offered || [],
    employment_start_date: prof?.employment_start_date || '',
  }
}

const emptyForm = {
  display_name: '',
  short_bio: '',
  academic_qualification_level: '',
  professional_qualification_entries: [],
  services_offered: [],
  employment_start_date: '',
}

function QualificationCards({ entries, onChange, disabled }) {
  const [draft, setDraft] = useState({ kind: 'degree', title: '', year: '' })

  function addCard() {
    const next = addQualificationEntry(entries, draft)
    if (next.length === entries.length) return
    onChange(next)
    setDraft({ kind: draft.kind, title: '', year: '' })
  }

  return (
    <div>
      <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Professional qualifications</p>
      <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 10px' }}>
        Add one degree or certification at a time. At least one degree with a year is needed to publish automatically.
      </p>
      {entries.length ? (
        <ul className="tp-qual-cards">
          {entries.map((entry, index) => (
            <li key={`${entry.kind}-${entry.title}-${index}`} className="tp-qual-card">
              <div>
                <strong>{entry.kind === 'degree' ? 'Degree' : 'Certification'}</strong>
                <p>
                  {entry.title}
                  {entry.year ? ` · ${entry.year}` : ''}
                </p>
              </div>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(removeQualificationEntry(entries, index))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="tp-qual-add">
        <select
          value={draft.kind}
          disabled={disabled}
          onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
        >
          <option value="degree">Degree</option>
          <option value="certificate">Certification</option>
        </select>
        <input
          placeholder={draft.kind === 'degree' ? 'Degree title' : 'Certification title'}
          value={draft.title}
          disabled={disabled}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
        />
        <input
          placeholder="Year"
          inputMode="numeric"
          maxLength={4}
          value={draft.year}
          disabled={disabled}
          onChange={(e) => setDraft({ ...draft, year: e.target.value.replace(/\D/g, '').slice(0, 4) })}
        />
        <button type="button" disabled={disabled || !draft.title.trim() || draft.year.length !== 4} onClick={addCard}>
          Add
        </button>
      </div>
    </div>
  )
}

export function TherapistServiceProfileSection({
  onProfileUpdated,
  editRequestKey = null,
  onEditRequestHandled,
  onListingDraft,
  liveQuality = null,
  sectionClassName = '',
}) {
  const [editing, setEditing] = useState(false)
  const [categories, setCategories] = useState([])
  const [profile, setProfile] = useState(null)
  const [form, setForm] = useState(emptyForm)
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
    const next = publishedFormFromRecord(prof)
    setForm(next)
    onListingDraft?.(profileFormFromRecord(prof))
  }

  useEffect(() => {
    load().catch(() => setError('Could not load service profile'))
  }, [])

  const paused = profile?.status === 'PAUSED'

  useEffect(() => {
    if (!editRequestKey || !profile || paused) return
    const next = profileFormFromRecord(profile)
    setForm(next)
    onListingDraft?.(next)
    setEditing(true)
    setError('')
    setSuccess('')
    onEditRequestHandled?.()
  }, [editRequestKey, profile, paused, onEditRequestHandled, onListingDraft])

  useEffect(() => {
    if (editing) onListingDraft?.(form)
  }, [editing, form, onListingDraft])

  const awaitingFirstApproval = profile?.status === 'PENDING' && !profile?.approved_snapshot
  const hasPendingChanges = Boolean(profile?.has_pending_changes)
  const statusKey = profile?.status === 'CHANGES_REQUESTED' ? 'CHANGES_REQUESTED' : hasPendingChanges ? 'PENDING' : profile?.status
  const st = PROFILE_STATUS[statusKey] || PROFILE_STATUS.DRAFT
  const quality = liveQuality || profile?.quality
  const words = wordCount(form.short_bio)
  const helper = submitHelperText(quality)
  const canSubmit = !quality || quality.can_submit

  function openEdit() {
    const next = profileFormFromRecord(profile)
    setForm(next)
    onListingDraft?.(next)
    setEditing(true)
    setError('')
    setSuccess('')
  }

  function cancelEdit() {
    const next = publishedFormFromRecord(profile)
    setForm(next)
    onListingDraft?.(profileFormFromRecord(profile))
    setEditing(false)
    setError('')
  }

  async function submitForApproval(e) {
    e.preventDefault()
    if (!canSubmit) {
      setError(helper)
      return
    }
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const updated = await apiFetch('/api/v1/therapist/profile/submit', {
        method: 'POST',
        body: JSON.stringify({
          display_name: form.display_name.trim(),
          short_bio: form.short_bio.trim() || null,
          academic_qualification_level: form.academic_qualification_level || null,
          professional_qualification_entries: form.professional_qualification_entries,
          services_offered: form.services_offered,
          employment_start_date: form.employment_start_date || null,
        }),
      })
      setProfile(updated)
      setForm(publishedFormFromRecord(updated))
      onListingDraft?.(profileFormFromRecord(updated))
      setEditing(false)
      if (updated.quality?.auto_pass || updated.status === 'APPROVED') {
        setSuccess(updated.has_pending_changes ? 'Sent for admin review. Your live listing stays unchanged until approved.' : 'Published. Families can see this listing.')
      } else {
        setSuccess('Submitted for admin approval. Your live listing stays unchanged until approved.')
      }
      await onProfileUpdated?.()
    } catch (err) {
      const detail = err.detail
      if (detail?.reminders?.length) {
        setError([detail.message, ...detail.reminders].filter(Boolean).join(' '))
      } else {
        setError(err.message || 'Could not submit')
      }
    } finally {
      setSaving(false)
    }
  }

  const viewForm = publishedFormFromRecord(profile)
  const serviceNames = serviceLabels(categories, viewForm.services_offered)

  return (
    <section id="therapist-profile-service" className={`therapist-profile__card${sectionClassName}`}>
      <style>{`
        .tp-qual-cards { list-style: none; margin: 0 0 12px; padding: 0; display: flex; flex-direction: column; gap: 8px; }
        .tp-qual-card { display: flex; justify-content: space-between; gap: 12px; align-items: center; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 12px; }
        .tp-qual-card p { margin: 4px 0 0; font-size: 0.85rem; color: #334155; }
        .tp-qual-card button, .tp-qual-add button { min-height: 44px; border-radius: 8px; border: 1px solid #c7d2fe; background: #eef2ff; color: #3730a3; font-weight: 600; }
        .tp-qual-add { display: grid; grid-template-columns: 1fr; gap: 8px; }
        @media (min-width: 720px) { .tp-qual-add { grid-template-columns: 140px 1fr 88px auto; } }
        .tp-qual-add input, .tp-qual-add select { padding: 8px 12px; border-radius: 8px; border: 1px solid #d1d5db; font-size: 0.875rem; min-height: 44px; }
      `}</style>
      <div className="therapist-profile__card-head">
        <div>
          <h2>Service profile</h2>
          <p className="therapist-profile__card-hint" style={{ marginTop: 4, marginBottom: 0 }}>
            Public-facing listing for families. Improve the quality score before you submit.
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
          {profile.status === 'CHANGES_REQUESTED'
            ? 'Your case team asked for a few updates before this can go live. '
            : 'Admin note: '}
          {profile.admin_note}
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
            <span className="therapist-profile__field-label">Display name</span>
            <span className="therapist-profile__field-value">{viewForm.display_name || '—'}</span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">What your Clients see about you</span>
            <span className={`therapist-profile__field-value ${!viewForm.short_bio ? 'therapist-profile__field-value--empty' : ''}`}>
              {viewForm.short_bio || 'Add a public bio'}
            </span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Highest qualification</span>
            <span className={`therapist-profile__field-value ${!viewForm.academic_qualification_level ? 'therapist-profile__field-value--empty' : ''}`}>
              {qualificationLevelLabel(viewForm.academic_qualification_level) || 'Select your highest level'}
            </span>
          </div>
          <div className="therapist-profile__field">
            <span className="therapist-profile__field-label">Qualifications</span>
            {viewForm.professional_qualification_entries.length ? (
              <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: '0.875rem' }}>
                {viewForm.professional_qualification_entries.map((entry) => (
                  <li key={`${entry.kind}-${entry.title}`}>
                    {entry.kind === 'degree' ? 'Degree' : 'Certification'}: {entry.title}
                    {entry.year ? ` (${entry.year})` : ''}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="therapist-profile__field-value therapist-profile__field-value--empty">Add a degree</span>
            )}
          </div>
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
          What your Clients see about you
          <textarea
            value={form.short_bio}
            onChange={(e) => setForm({ ...form, short_bio: e.target.value })}
            disabled={paused}
            rows={5}
            maxLength={800}
            placeholder="Write more than 40 words about how you support children and families."
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }}
          />
          <span style={{ fontSize: '0.75rem', color: words > 40 ? '#15803d' : '#b45309' }}>
            {words} words · more than 40 needed
          </span>
        </label>

        <div>
          <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Highest qualification</p>
          <QualificationLevelPicker
            value={form.academic_qualification_level}
            onChange={(academic_qualification_level) => setForm({ ...form, academic_qualification_level })}
            disabled={paused}
          />
        </div>

        <QualificationCards
          entries={form.professional_qualification_entries}
          disabled={paused}
          onChange={(professional_qualification_entries) => setForm({ ...form, professional_qualification_entries })}
        />

        <div>
          <p style={{ fontSize: '0.875rem', fontWeight: 500, marginBottom: 8 }}>Services offered</p>
          <ServiceCategoryPicker
            categories={categories}
            value={form.services_offered}
            onChange={(services_offered) => setForm({ ...form, services_offered })}
            disabled={paused}
          />
        </div>

        <p style={{ fontSize: '0.8rem', color: '#475569', margin: 0 }}>{helper}</p>
        <div className="therapist-profile__form-actions">
          <button type="submit" className="therapist-profile__edit-btn" disabled={saving || paused || !canSubmit}>
            {saving ? 'Submitting…' : quality?.auto_pass ? 'Publish now' : 'Submit for approval'}
          </button>
          <button type="button" className="therapist-profile__cancel" disabled={saving} onClick={cancelEdit}>
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
