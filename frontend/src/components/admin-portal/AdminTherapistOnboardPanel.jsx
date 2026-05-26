import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPanel } from './ui/index.js'

function defaultTherapistServices(roleDefaults) {
  const fromRole = roleDefaults?.THERAPIST
  if (fromRole?.services?.length) return [...fromRole.services]
  if (Array.isArray(fromRole) && fromRole.length) return [...fromRole]
  return []
}

function buildEmptyForm(roleDefaults) {
  return {
    full_name: '',
    email: '',
    phone: '',
    mode: 'invite',
    password: '',
    send_email: true,
    services_offered: defaultTherapistServices(roleDefaults),
    primary_case_manager_user_id: '',
    mentor_user_id: '',
    short_bio: '',
  }
}

function parseBulkLines(text) {
  const lines = text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
  return lines.map((line) => {
    const parts = line.includes('\t') ? line.split('\t') : line.split(',').map((p) => p.trim())
    const [full_name, email, phone = '', servicesRaw = ''] = parts
    const services_offered = servicesRaw
      ? servicesRaw.split(/[|;]/).map((s) => s.trim().toLowerCase()).filter(Boolean)
      : []
    return { full_name: full_name || '', email: email || '', phone, services_offered }
  })
}

function parseCsvFile(text) {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean)
  if (lines.length === 0) return ''
  const headerLine = lines[0].toLowerCase()
  const isHeader = headerLine.includes('full name') || headerLine.includes('email') || headerLine.includes('name')
  const dataLines = isHeader ? lines.slice(1) : lines
  return dataLines.join('\n')
}

export function AdminTherapistOnboardPanel({
  roleDefaults,
  pendingInvites,
  onSuccess,
  onError,
  onReload,
}) {
  const [serviceCategories, setServiceCategories] = useState([])
  const [caseManagers, setCaseManagers] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [showBulk, setShowBulk] = useState(false)
  const [form, setForm] = useState(() => buildEmptyForm(roleDefaults))
  const [bulkPrimaryCmId, setBulkPrimaryCmId] = useState('')
  const [bulkText, setBulkText] = useState('')
  const [bulkMode, setBulkMode] = useState('invite')
  const [bulkResults, setBulkResults] = useState(null)
  const [bulkPreview, setBulkPreview] = useState(null)
  const [bulkPhase, setBulkPhase] = useState('edit')
  const [lastResult, setLastResult] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    apiFetch('/api/v1/therapist/service-categories')
      .then(setServiceCategories)
      .catch(() => setServiceCategories([]))
    apiFetch('/api/v1/admin/users/directory?roles=CASE_MANAGER,MODULE_ADMIN')
      .then((rows) => setCaseManagers(Array.isArray(rows) ? rows : []))
      .catch(() => setCaseManagers([]))
  }, [])

  function resetForm() {
    setForm(buildEmptyForm(roleDefaults))
  }

  function toggleService(id) {
    setForm((f) => ({
      ...f,
      services_offered: f.services_offered.includes(id)
        ? f.services_offered.filter((s) => s !== id)
        : [...f.services_offered, id],
    }))
  }

  async function submitAdd(e) {
    e.preventDefault()
    if (!form.primary_case_manager_user_id) {
      onError('Select a primary case manager')
      return
    }
    if (!form.services_offered.length) {
      onError('Select at least one service')
      return
    }
    setSubmitting(true)
    onError('')
    try {
      const res = await apiFetch('/api/v1/admin/therapists/onboard', {
        method: 'POST',
        body: JSON.stringify({
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          phone: form.phone.trim() || null,
          mode: form.mode,
          password: form.mode === 'direct' && form.password ? form.password : null,
          send_email: form.send_email,
          module_assignments: form.services_offered,
          services_offered: form.services_offered,
          primary_case_manager_user_id: Number(form.primary_case_manager_user_id),
          mentor_user_id: form.mentor_user_id ? Number(form.mentor_user_id) : null,
          short_bio: form.short_bio.trim() || null,
        }),
      })
      setLastResult(res)
      if (res.invite_url) onSuccess(`Invite created for ${form.email}`)
      else onSuccess(`Therapist account created (ID ${res.user_id})`)
      resetForm()
      setShowAdd(false)
      onReload()
    } catch (err) {
      onError(err.message || 'Could not add therapist')
    } finally {
      setSubmitting(false)
    }
  }

  function buildBulkRows() {
    return parseBulkLines(bulkText).filter((r) => r.email && r.full_name)
  }

  function goBulkPreview(e) {
    e?.preventDefault()
    const rows = buildBulkRows()
    if (!rows.length) {
      onError('Add at least one row: Name, email, phone, services')
      return
    }
    onError('')
    setBulkPreview(rows)
    setBulkPhase('preview')
  }

  async function confirmBulkUpload() {
    const rows = bulkPreview || buildBulkRows()
    if (!rows.length) return
    if (!bulkPrimaryCmId) {
      onError('Select a primary case manager for bulk upload')
      return
    }
    setSubmitting(true)
    onError('')
    try {
      const defaultServices = defaultTherapistServices(roleDefaults)
      const results = await apiFetch('/api/v1/admin/therapists/bulk-onboard', {
        method: 'POST',
        body: JSON.stringify({
          mode: bulkMode,
          send_email: true,
          primary_case_manager_user_id: Number(bulkPrimaryCmId),
          therapists: rows.map((r) => ({
            ...r,
            module_assignments: r.services_offered?.length ? r.services_offered : defaultServices,
            services_offered: r.services_offered?.length ? r.services_offered : defaultServices,
          })),
        }),
      })
      setBulkResults(results)
      setBulkPhase('done')
      const ok = results.filter((r) => r.success).length
      onSuccess(`${ok} of ${results.length} therapists processed`)
      onReload()
    } catch (err) {
      onError(err.message || 'Bulk upload failed')
    } finally {
      setSubmitting(false)
    }
  }

  function closeBulk() {
    setShowBulk(false)
    setBulkPhase('edit')
    setBulkPreview(null)
    setBulkResults(null)
    setBulkText('')
  }

  function copyLink(url) {
    navigator.clipboard?.writeText(url)
    onSuccess('Link copied')
  }

  return (
    <>
      <div className="admin-btn-group" style={{ marginBottom: 12 }}>
        <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => { resetForm(); setShowAdd(true) }}>
          Add therapist
        </button>
        <button
          type="button"
          className="admin-btn admin-btn--secondary admin-btn--sm"
          onClick={() => {
            setBulkResults(null)
            setBulkPreview(null)
            setBulkPhase('edit')
            setShowBulk(true)
          }}
        >
          Bulk upload
        </button>
      </div>

      {lastResult?.invite_url || lastResult?.temporary_password ? (
        <p className="admin-alert" style={{ wordBreak: 'break-all', fontSize: '0.875rem' }}>
          {lastResult.invite_url ? (
            <>
              Invite:{' '}
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => copyLink(lastResult.invite_url)}>
                Copy link
              </button>{' '}
              {lastResult.invite_url}
            </>
          ) : null}
          {lastResult.temporary_password ? (
            <span> Temporary password: <strong>{lastResult.temporary_password}</strong></span>
          ) : null}
        </p>
      ) : null}

      {pendingInvites.length > 0 ? (
        <AdminPanel title={`Pending therapist invites (${pendingInvites.length})`} subtitle="Links expire after 7 days">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Expires</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {pendingInvites.map((inv) => (
                <tr key={inv.id}>
                  <td>{inv.email}</td>
                  <td>{new Date(inv.expires_at).toLocaleDateString()}</td>
                  <td>
                    <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => copyLink(inv.invite_url)}>
                      Copy link
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </AdminPanel>
      ) : null}

      {showAdd ? (
        <div className="admin-drawer-backdrop" role="presentation" onClick={() => setShowAdd(false)}>
          <div className="admin-drawer" role="dialog" aria-labelledby="add-therapist-title" onClick={(e) => e.stopPropagation()}>
            <header className="admin-drawer__header">
              <h2 id="add-therapist-title">Add therapist</h2>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setShowAdd(false)} aria-label="Close">
                Close
              </button>
            </header>
            <form onSubmit={submitAdd} className="admin-form-grid admin-drawer__body">
              <label>
                Full name
                <input className="admin-input" value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} required />
              </label>
              <label>
                Email
                <input type="email" className="admin-input" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} required />
              </label>
              <label>
                Phone
                <input className="admin-input" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
              </label>
              <label>
                Onboarding
                <select className="admin-input" value={form.mode} onChange={(e) => setForm((f) => ({ ...f, mode: e.target.value }))}>
                  <option value="invite">Email invite link</option>
                  <option value="direct">Create account now</option>
                </select>
              </label>
              {form.mode === 'direct' ? (
                <label>
                  Password (optional — auto-generated if blank)
                  <input type="password" className="admin-input" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} minLength={6} />
                </label>
              ) : (
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" checked={form.send_email} onChange={(e) => setForm((f) => ({ ...f, send_email: e.target.checked }))} />
                  Send invite email
                </label>
              )}
              <label>
                Primary case manager
                <select
                  className="admin-input"
                  value={form.primary_case_manager_user_id}
                  onChange={(e) => setForm((f) => ({ ...f, primary_case_manager_user_id: e.target.value }))}
                  required
                >
                  <option value="">Select case manager…</option>
                  {caseManagers.map((cm) => (
                    <option key={cm.id} value={cm.id}>
                      {cm.full_name} ({cm.email})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Mentor (optional)
                <select
                  className="admin-input"
                  value={form.mentor_user_id}
                  onChange={(e) => setForm((f) => ({ ...f, mentor_user_id: e.target.value }))}
                >
                  <option value="">None</option>
                  {caseManagers.map((cm) => (
                    <option key={`m-${cm.id}`} value={cm.id}>
                      {cm.full_name}
                    </option>
                  ))}
                </select>
              </label>
              <div style={{ gridColumn: '1 / -1' }}>
                <p className="admin-muted" style={{ marginBottom: 8 }}>Services this therapist delivers</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {serviceCategories.map((s) => (
                    <label key={s.id} className="admin-chip" style={{ cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={form.services_offered.includes(s.id)}
                        onChange={() => toggleService(s.id)}
                        style={{ marginRight: 6 }}
                      />
                      {s.label}
                    </label>
                  ))}
                </div>
              </div>
              <label style={{ gridColumn: '1 / -1' }}>
                Short bio (optional)
                <textarea className="admin-input" rows={2} value={form.short_bio} onChange={(e) => setForm((f) => ({ ...f, short_bio: e.target.value }))} />
              </label>
              <div className="admin-btn-group" style={{ gridColumn: '1 / -1' }}>
                <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={submitting}>
                  {submitting ? 'Saving…' : form.mode === 'invite' ? 'Send invite' : 'Create therapist'}
                </button>
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setShowAdd(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {showBulk ? (
        <div
          className="admin-drawer-backdrop"
          role="presentation"
          onClick={() => {
            if (bulkPhase !== 'done') closeBulk()
          }}
        >
          <div className="admin-drawer admin-drawer--wide" role="dialog" aria-labelledby="bulk-therapist-title" onClick={(e) => e.stopPropagation()}>
            <header className="admin-drawer__header">
              <h2 id="bulk-therapist-title">Bulk upload therapists</h2>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={closeBulk} aria-label="Close">
                Close
              </button>
            </header>
            <div className="admin-drawer__body">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                <p className="admin-muted" style={{ margin: 0 }}>
                  One row per therapist: <code>Full Name, Email, Phone, Services (pipe-separated)</code>
                </p>
                <div className="admin-btn-group">
                  <a
                    href="/api/v1/admin/therapists/bulk-template.csv"
                    download="therapist_bulk_template.csv"
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                  >
                    ↓ CSV template
                  </a>
                  <a
                    href="/api/v1/admin/therapists/bulk-template.xlsx"
                    download="therapist_bulk_template.xlsx"
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                  >
                    ↓ XLSX template
                  </a>
                </div>
              </div>
              <label style={{ marginBottom: 12 }}>
                Upload file (.csv or .xlsx)
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  className="admin-input"
                  style={{ marginTop: 4 }}
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    const isCsv = file.name.endsWith('.csv') || file.type === 'text/csv'
                    if (isCsv) {
                      const reader = new FileReader()
                      reader.onload = (ev) => {
                        const parsed = parseCsvFile(ev.target.result)
                        setBulkText(parsed)
                      }
                      reader.readAsText(file)
                    } else {
                      setBulkText('')
                      onError('For XLSX, use the XLSX template or export sheet 1 as CSV, then upload.')
                    }
                    e.target.value = ''
                  }}
                />
              </label>
              <label>
                Primary case manager (all rows)
                <select
                  className="admin-input"
                  value={bulkPrimaryCmId}
                  onChange={(e) => setBulkPrimaryCmId(e.target.value)}
                  required
                >
                  <option value="">Select case manager…</option>
                  {caseManagers.map((cm) => (
                    <option key={cm.id} value={cm.id}>
                      {cm.full_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Mode
                <select className="admin-input" value={bulkMode} onChange={(e) => setBulkMode(e.target.value)} style={{ maxWidth: 240 }}>
                  <option value="invite">Invite links</option>
                  <option value="direct">Create accounts</option>
                </select>
              </label>
              {bulkPhase === 'preview' && bulkPreview?.length ? (
                <table className="admin-table" style={{ marginBottom: 16 }}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Phone</th>
                      <th>Services</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bulkPreview.map((r) => (
                      <tr key={r.email}>
                        <td>{r.full_name}</td>
                        <td>{r.email}</td>
                        <td>{r.phone || '—'}</td>
                        <td>{(r.services_offered || []).join(' | ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}

              {bulkPhase === 'edit' ? (
                <>
                  <textarea
                    className="admin-input"
                    rows={10}
                    placeholder={'Jane Doe, jane@example.com, +91 98765 43210, shadow|homecare\nJohn Smith, john@example.com,, speech_therapy'}
                    value={bulkText}
                    onChange={(e) => setBulkText(e.target.value)}
                    style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.85rem' }}
                  />
                  <div className="admin-btn-group" style={{ marginTop: 12 }}>
                    <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={goBulkPreview}>
                      Preview rows
                    </button>
                    <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={closeBulk}>
                      Cancel
                    </button>
                  </div>
                </>
              ) : null}

              {bulkPhase === 'preview' ? (
                <div className="admin-btn-group" style={{ marginTop: 12 }}>
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={submitting} onClick={confirmBulkUpload}>
                    {submitting ? 'Uploading…' : `Confirm upload (${bulkPreview?.length || 0})`}
                  </button>
                  <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setBulkPhase('edit')}>
                    Back
                  </button>
                </div>
              ) : null}

              {bulkPhase === 'done' && bulkResults?.length ? (
                <div className="admin-btn-group" style={{ marginTop: 12 }}>
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={closeBulk}>
                    Done
                  </button>
                </div>
              ) : null}

              {bulkResults?.length ? (
                <table className="admin-table" style={{ marginTop: 16 }}>
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Status</th>
                      <th>ID / link</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bulkResults.map((r) => (
                      <tr key={r.email}>
                        <td>{r.email}</td>
                        <td>{r.success ? 'OK' : r.error}</td>
                        <td>
                          {r.user_id ? `User #${r.user_id}` : null}
                          {r.invite_url ? (
                            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => copyLink(r.invite_url)}>
                              Copy link
                            </button>
                          ) : null}
                          {r.temporary_password ? <span className="admin-muted"> pwd: {r.temporary_password}</span> : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
