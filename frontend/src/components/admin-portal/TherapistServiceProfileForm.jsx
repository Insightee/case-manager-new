import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'

/**
 * Shared therapist service profile fields (admin create + therapist edit).
 */
export function TherapistServiceProfileForm({ form, setForm, categories, showTherapistSelect, therapists = [] }) {
  return (
    <>
      {showTherapistSelect ? (
        <label>
          Therapist
          <select required value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })}>
            <option value="">Select…</option>
            {therapists.map((t) => (
              <option key={t.id} value={t.id}>
                {t.full_name} ({t.email})
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <label>
        Display name
        <input required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
      </label>
      <label style={{ gridColumn: '1 / -1' }}>
        Short bio
        <textarea value={form.short_bio} onChange={(e) => setForm({ ...form, short_bio: e.target.value })} rows={2} />
      </label>
      <label style={{ gridColumn: '1 / -1' }}>
        Qualifications
        <textarea
          value={form.academic_qualifications}
          onChange={(e) => setForm({ ...form, academic_qualifications: e.target.value })}
          rows={2}
        />
      </label>
      <label style={{ gridColumn: '1 / -1' }}>
        Certificates (one per line)
        <textarea
          value={form.professional_certificates}
          onChange={(e) => setForm({ ...form, professional_certificates: e.target.value })}
          rows={2}
        />
      </label>
      <div style={{ gridColumn: '1 / -1' }}>
        <p className="admin-drawer__subtitle">Services</p>
        <ServiceCategoryPicker
          categories={categories}
          value={form.services_offered}
          onChange={(services_offered) => setForm({ ...form, services_offered })}
        />
      </div>
    </>
  )
}
