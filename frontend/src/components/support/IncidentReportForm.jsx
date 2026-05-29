import { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { defaultPriorityForSubcategory } from '../../lib/incidentCatalog.js'

function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileKey(file) {
  return `${file.name}-${file.size}-${file.lastModified}`
}

function isImageFile(file) {
  return (file.type || '').startsWith('image/')
}

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
  hideServiceType = false,
  onSubmit,
  submitting = false,
  error = '',
}) {
  const [meta, setMeta] = useState(null)
  const [form, setForm] = useState(() => ({ ...EMPTY_FORM, incident_at: toLocalDatetimeInput() }))
  const [files, setFiles] = useState([])
  const fileInputRef = useRef(null)

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

  useEffect(() => {
    if (!form.case_id) return
    const match = cases.find((c) => String(c.id) === String(form.case_id))
    if (!match) return
    const derived = match.service_type || match.product_module || match.productModule
    if (derived) {
      setForm((f) => (f.service_type === derived ? f : { ...f, service_type: derived }))
    }
  }, [form.case_id, cases])

  function handleCategoryChange(cat) {
    setForm((f) => ({ ...f, primary_category: cat, subcategory: '' }))
  }

  function removeFile(target) {
    setFiles((prev) => prev.filter((f) => fileKey(f) !== fileKey(target)))
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function addFiles(fileList) {
    const incoming = Array.from(fileList || [])
    if (!incoming.length) return
    setFiles((prev) => {
      const seen = new Set(prev.map(fileKey))
      const merged = [...prev]
      for (const f of incoming) {
        const key = fileKey(f)
        if (!seen.has(key)) {
          seen.add(key)
          merged.push(f)
        }
      }
      return merged
    })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const incidentAt = form.incident_at ? new Date(form.incident_at).toISOString() : new Date().toISOString()
    const selectedCase = cases.find((c) => String(c.id) === String(form.case_id))
    const derivedServiceType =
      selectedCase?.service_type || selectedCase?.product_module || selectedCase?.productModule || form.service_type
    const serviceType = hideServiceType ? derivedServiceType : form.service_type || derivedServiceType
    const payload = {
      case_id: form.case_id ? Number(form.case_id) : undefined,
      primary_category: form.primary_category,
      subcategory: form.subcategory,
      what_happened: form.what_happened.trim(),
      priority: form.priority,
      incident_at: incidentAt,
      location: form.location,
      immediate_action: form.immediate_action.trim() || undefined,
      child_safe: form.child_safe,
      parent_informed: form.parent_informed,
      files,
      attachment_note: form.attachment_note.trim() || undefined,
    }
    if (serviceType) payload.service_type = serviceType
    await onSubmit(payload)
  }

  if (!meta) {
    return <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Loading form…</p>
  }

  return (
    <form onSubmit={handleSubmit} className="incident-report-form">
      {cases.length > 0 ? (
        <label className="parent-support__field">
          Case {caseRequired ? '(required)' : '(optional)'}
          <select
            required={caseRequired}
            value={form.case_id}
            onChange={(e) => setForm({ ...form, case_id: e.target.value })}
          >
            <option value="">{caseRequired ? 'Select client…' : 'Not linked to a specific case'}</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                {[c.case_code, c.child_name || c.childName, c.service_type || c.serviceType]
                  .filter(Boolean)
                  .join(' · ')}
              </option>
            ))}
          </select>
        </label>
      ) : caseRequired ? (
        <p style={{ color: '#b45309', fontSize: '0.875rem' }}>You have no active cases assigned. Contact your case manager before filing an incident.</p>
      ) : null}

      {!hideServiceType ? (
        <label className="parent-support__field">
          Service type
          <select value={form.service_type} onChange={(e) => setForm({ ...form, service_type: e.target.value })}>
            {meta.service_types.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
        </label>
      ) : null}

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

      <div className="parent-support__field incident-report-form__attachments">
        <span className="incident-report-form__attachments-label">Attach files</span>
        <p className="incident-report-form__attachments-hint">
          Images, PDF, documents, audio, or video (max 15 MB each, up to 8 files)
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="incident-report-form__file-input"
          accept="image/*,application/pdf,video/*,audio/*,.doc,.docx,.txt"
          onChange={(e) => {
            addFiles(e.target.files)
            if (fileInputRef.current) fileInputRef.current.value = ''
          }}
        />
        <button
          type="button"
          className="incident-report-form__file-trigger"
          onClick={() => fileInputRef.current?.click()}
          disabled={submitting}
        >
          Choose files
        </button>
        {files.length > 0 ? (
          <ul className="incident-report-form__file-list" aria-live="polite">
            {files.map((f) => (
              <li key={fileKey(f)} className="incident-report-form__file-item">
                {isImageFile(f) ? (
                  <img
                    className="incident-report-form__file-thumb"
                    src={URL.createObjectURL(f)}
                    alt=""
                    onLoad={(e) => URL.revokeObjectURL(e.target.src)}
                  />
                ) : (
                  <span className="incident-report-form__file-icon" aria-hidden>
                    📎
                  </span>
                )}
                <div className="incident-report-form__file-meta">
                  <span className="incident-report-form__file-name">{f.name}</span>
                  <span className="incident-report-form__file-size">{formatFileSize(f.size)}</span>
                </div>
                <button
                  type="button"
                  className="incident-report-form__file-remove"
                  onClick={() => removeFile(f)}
                  aria-label={`Remove ${f.name}`}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="incident-report-form__file-empty">No files selected yet.</p>
        )}
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

      {error ? <p className="incident-report-form__error" role="alert">{error}</p> : null}

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
