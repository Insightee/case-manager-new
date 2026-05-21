import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { defaultPriorityForSubcategory } from '../../lib/incidentCatalog.js'

const EMPTY_FORM = {
  case_id: '',
  service_type: 'homecare',
  incident_at: '',
  location: 'home',
  primary_category: '',
  subcategory: '',
  priority: 'NORMAL',
  what_happened: '',
  immediate_action: '',
  child_safe: 'yes',
  parent_informed: 'na',
  attachment_note: '',
}

function toLocalDatetimeInput(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function IncidentReportForm({
  cases = [],
  caseRequired = false,
  onSubmit,
  submitting = false,
  error = '',
}) {
  const [meta, setMeta] = useState(null)
  const [form, setForm] = useState(() => ({ ...EMPTY_FORM, incident_at: toLocalDatetimeInput() }))
  const [files, setFiles] = useState([])

  useEffect(() => {
    apiFetch('/api/v1/incidents/meta')
      .then(setMeta)
      .catch(() => setMeta(null))
  }, [])

  const subcategories = useMemo(() => {
    if (!meta || !form.primary_category) return []
    return meta.subcategories_by_category[form.primary_category] || []
  }, [meta, form.primary_category])

  useEffect(() => {
    if (form.subcategory) {
      setForm((f) => ({ ...f, priority: defaultPriorityForSubcategory(f.subcategory) }))
    }
  }, [form.subcategory])

  function handleCategoryChange(cat) {
    setForm((f) => ({ ...f, primary_category: cat, subcategory: '' }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const incidentAt = form.incident_at ? new Date(form.incident_at).toISOString() : new Date().toISOString()
    await onSubmit({
      case_id: form.case_id ? Number(form.case_id) : undefined,
      primary_category: form.primary_category,
      subcategory: form.subcategory,
      what_happened: form.what_happened.trim(),
      priority: form.priority,
      service_type: form.service_type,
      incident_at: incidentAt,
      location: form.location,
      immediate_action: form.immediate_action.trim() || undefined,
      child_safe: form.child_safe,
      parent_informed: form.parent_informed,
      files,
      attachment_note: form.attachment_note.trim() || undefined,
    })
  }

  if (!meta) {
    return <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Loading form…</p>
  }

  return (
    <form onSubmit={handleSubmit} className="incident-report-form">
      {cases.length > 0 ? (
        <label className="parent-support__field">
          Child / client {caseRequired ? '(required)' : '(optional)'}
          <select
            required={caseRequired}
            value={form.case_id}
            onChange={(e) => setForm({ ...form, case_id: e.target.value })}
          >
            <option value="">{caseRequired ? 'Select client…' : 'Not linked to a specific case'}</option>
            {cases.map((c) => (
              <option key={c.id || c.case_id} value={c.id || c.case_id}>
                {c.child_name || c.childName || c.case_code}
                {c.case_code ? ` · ${c.case_code}` : ''}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <label className="parent-support__field">
        Service type
        <select value={form.service_type} onChange={(e) => setForm({ ...form, service_type: e.target.value })}>
          {meta.service_types.map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
      </label>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label className="parent-support__field">
          Date & time
          <input
            type="datetime-local"
            required
            value={form.incident_at}
            onChange={(e) => setForm({ ...form, incident_at: e.target.value })}
          />
        </label>
        <label className="parent-support__field">
          Location
          <select value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })}>
            {meta.locations.map((l) => (
              <option key={l.key} value={l.key}>{l.label}</option>
            ))}
          </select>
        </label>
      </div>

      <label className="parent-support__field">
        Primary category
        <select
          required
          value={form.primary_category}
          onChange={(e) => handleCategoryChange(e.target.value)}
        >
          <option value="">Select category…</option>
          {meta.primary_categories.map((c) => (
            <option key={c.key} value={c.key}>{c.label}</option>
          ))}
        </select>
      </label>

      <label className="parent-support__field">
        Subcategory
        <select
          required
          disabled={!form.primary_category}
          value={form.subcategory}
          onChange={(e) => setForm({ ...form, subcategory: e.target.value })}
        >
          <option value="">Select subcategory…</option>
          {subcategories.map((s) => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
      </label>

      <label className="parent-support__field">
        Priority
        <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
          {meta.priorities.map((p) => (
            <option key={p.key} value={p.key}>{p.label}</option>
          ))}
        </select>
      </label>

      <label className="parent-support__field">
        What happened?
        <textarea
          required
          minLength={3}
          rows={5}
          value={form.what_happened}
          onChange={(e) => setForm({ ...form, what_happened: e.target.value })}
          placeholder="Describe what happened, who was involved, and context…"
        />
      </label>

      <label className="parent-support__field">
        Immediate action taken
        <textarea
          rows={2}
          value={form.immediate_action}
          onChange={(e) => setForm({ ...form, immediate_action: e.target.value })}
          placeholder="Optional — first aid, supervision, who you contacted…"
        />
      </label>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <label className="parent-support__field">
          Is the child safe now?
          <select value={form.child_safe} onChange={(e) => setForm({ ...form, child_safe: e.target.value })}>
            {meta.yes_no_na.map((o) => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </select>
        </label>
        <label className="parent-support__field">
          Was parent informed?
          <select value={form.parent_informed} onChange={(e) => setForm({ ...form, parent_informed: e.target.value })}>
            {meta.yes_no_na.map((o) => (
              <option key={o.key} value={o.key}>{o.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="parent-support__field">
        <span style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>Attach files</span>
        <p style={{ margin: '0 0 8px', fontSize: '0.78rem', color: '#64748b' }}>
          Images, PDF, documents, audio, or video (max 15 MB each)
        </p>
        <input
          type="file"
          multiple
          accept="image/*,application/pdf,video/*,audio/*,.doc,.docx,.txt"
          onChange={(e) => setFiles(Array.from(e.target.files || []))}
        />
        {files.length > 0 ? (
          <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: '0.8rem', color: '#475569' }}>
            {files.map((f) => (
              <li key={`${f.name}-${f.size}`}>{f.name}</li>
            ))}
          </ul>
        ) : null}
        <label className="parent-support__field" style={{ marginTop: 10 }}>
          Attachment note
          <input
            type="text"
            value={form.attachment_note}
            onChange={(e) => setForm({ ...form, attachment_note: e.target.value })}
            placeholder="Short note about the attachment(s)"
          />
        </label>
      </div>

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.8rem' }}>{error}</p> : null}

      <button
        type="submit"
        disabled={submitting}
        className="parent-support__submit"
        style={{ background: '#ef4444', borderColor: '#ef4444' }}
      >
        {submitting ? 'Submitting…' : 'Submit incident report'}
      </button>
    </form>
  )
}
