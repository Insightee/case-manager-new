import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { IncidentDetailPanel } from '../support/IncidentDetailPanel.jsx'
import '../support/support-tickets.css'
import '../client-portal/parent-support.css'

const STATUS_META = {
  OPEN: { label: 'Reported', bg: '#fef3c7', color: '#b45309' },
  INVESTIGATING: { label: 'Under review', bg: '#dbeafe', color: '#1d4ed8' },
  RESOLVED: { label: 'Resolved', bg: '#d1fae5', color: '#047857' },
  CLOSED: { label: 'Closed', bg: '#f1f5f9', color: '#64748b' },
}

function StatusPill({ status }) {
  const m = STATUS_META[status] || STATUS_META.OPEN
  return (
    <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', padding: '3px 8px', borderRadius: 6, background: m.bg, color: m.color }}>
      {m.label}
    </span>
  )
}

export function TherapistIncidentsPage() {
  const [cases, setCases] = useState([])
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [expandedDetail, setExpandedDetail] = useState(null)

  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [caseId, setCaseId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [formSuccess, setFormSuccess] = useState('')

  const loadIncidents = useCallback(async () => {
    setLoading(true)
    try {
      setIncidents(unwrapList(await apiFetch('/api/v1/incidents?page_size=100')))
    } catch {
      setIncidents([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadIncidents()
    apiFetch('/api/v1/cases/my').then(setCases).catch(() => setCases([]))
  }, [loadIncidents])

  const openIncidents = useMemo(
    () => incidents.filter((i) => i.status === 'OPEN' || i.status === 'INVESTIGATING'),
    [incidents],
  )
  const closedIncidents = useMemo(
    () => incidents.filter((i) => i.status === 'RESOLVED' || i.status === 'CLOSED'),
    [incidents],
  )

  async function toggleExpand(inc) {
    if (expandedId === inc.id) {
      setExpandedId(null)
      setExpandedDetail(null)
      return
    }
    setExpandedId(inc.id)
    try {
      setExpandedDetail(await apiFetch(`/api/v1/incidents/${inc.id}`))
    } catch {
      setExpandedDetail(null)
    }
  }

  function onDetailUpdated(updated) {
    setExpandedDetail(updated)
    loadIncidents()
  }

  async function submit(e) {
    e.preventDefault()
    if (!title.trim() || !description.trim()) return
    setSubmitting(true)
    setFormError('')
    setFormSuccess('')
    try {
      const created = await apiFetch('/api/v1/incidents', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          case_id: caseId ? Number(caseId) : undefined,
          is_sensitive: false,
        }),
      })
      setFormSuccess('Incident filed. The team will review and respond.')
      setTitle('')
      setDescription('')
      setCaseId('')
      setShowForm(false)
      setExpandedId(created.id)
      await loadIncidents()
      apiFetch(`/api/v1/incidents/${created.id}`).then(setExpandedDetail).catch(() => {})
    } catch (err) {
      setFormError(err.message || 'Could not file report')
    } finally {
      setSubmitting(false)
    }
  }

  function renderRow(inc) {
    const isExpanded = expandedId === inc.id
    return (
      <div
        key={inc.id}
        className="parent-support__ticket"
        style={{ boxShadow: isExpanded ? '0 0 0 2px #6366f1' : undefined }}
      >
        <div
          className="parent-support__ticket-head"
          role="button"
          tabIndex={0}
          onClick={() => toggleExpand(inc)}
          onKeyDown={(e) => e.key === 'Enter' && toggleExpand(inc)}
        >
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
              <StatusPill status={inc.status} />
              {inc.case_code ? (
                <span style={{ fontSize: '0.72rem', fontWeight: 700, background: '#eef2ff', color: '#3730a3', border: '1px solid #c7d2fe', borderRadius: 6, padding: '2px 7px', fontFamily: 'monospace' }}>
                  {inc.case_code}
                </span>
              ) : null}
              <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: '#94a3b8' }}>
                {new Date(inc.created_at).toLocaleDateString()}
              </span>
            </div>
            <p style={{ fontWeight: 600, margin: '0 0 2px', fontSize: '0.9rem', color: '#0f172a' }}>{inc.title}</p>
            {inc.child_name ? (
              <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b' }}>{inc.child_name}</p>
            ) : null}
          </div>
          <span style={{ color: '#94a3b8' }}>{isExpanded ? '▲' : '▼'}</span>
        </div>

        {isExpanded ? (
          <div style={{ borderTop: '1px solid #f1f5f9', padding: '0 16px 16px', background: '#fafafa' }}>
            {expandedDetail?.id === inc.id ? (
              <IncidentDetailPanel
                incident={expandedDetail}
                onUpdated={onDetailUpdated}
                apiBase="/api/v1/incidents"
                canManage={false}
              />
            ) : (
              <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: 12 }}>Loading…</p>
            )}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="parent-support">
      {/* Form card */}
      <section className="parent-support__form-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Incident Reporting</h2>
          <button
            type="button"
            onClick={() => { setShowForm((s) => !s); setFormError(''); setFormSuccess('') }}
            style={{ background: showForm ? '#f1f5f9' : '#ef4444', color: showForm ? '#475569' : '#fff', border: 'none', borderRadius: 10, padding: '8px 16px', fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer' }}
          >
            {showForm ? 'Cancel' : '+ File incident report'}
          </button>
        </div>
        <p className="parent-support__hint">
          Report any safety, conduct, or welfare concern related to your clients. The admin team will investigate and respond.
        </p>

        {showForm ? (
          <form onSubmit={submit} style={{ marginTop: 12 }}>
            {cases.length > 0 ? (
              <label className="parent-support__field">
                Related case (optional)
                <select value={caseId} onChange={(e) => setCaseId(e.target.value)}>
                  <option value="">Not linked to a specific case</option>
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.child_name || c.childName} ({c.case_code || c.caseId})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label className="parent-support__field">
              Incident title
              <input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Brief summary of the incident"
              />
            </label>
            <label className="parent-support__field">
              Full description
              <textarea
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what happened, when, who was involved, and any immediate actions taken…"
                rows={5}
              />
            </label>
            {formError ? <p style={{ color: '#b91c1c', fontSize: '0.8rem', marginBottom: 8 }}>{formError}</p> : null}
            <button
              type="submit"
              disabled={submitting}
              className="parent-support__submit"
              style={{ background: '#ef4444', borderColor: '#ef4444' }}
            >
              {submitting ? 'Filing…' : 'Submit incident report'}
            </button>
          </form>
        ) : null}

        {formSuccess ? (
          <p style={{ color: '#15803d', fontSize: '0.875rem', marginTop: 12 }}>{formSuccess}</p>
        ) : null}
      </section>

      {/* Active reports */}
      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Active reports ({openIncidents.length})</h2>
      {loading ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>Loading…</p>
      ) : openIncidents.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>No active incident reports.</p>
      ) : (
        openIncidents.map(renderRow)
      )}

      {/* Closed */}
      {closedIncidents.length > 0 ? (
        <>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '24px 0 12px' }}>Resolved / closed</h2>
          {closedIncidents.map(renderRow)}
        </>
      ) : null}

      {!loading && incidents.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 16px', background: '#fff', borderRadius: 14, border: '1px dashed #e2e8f0' }}>
          <p style={{ fontWeight: 600, color: '#475569', marginBottom: 4 }}>No incident reports</p>
          <p style={{ fontSize: '0.875rem', color: '#94a3b8' }}>Use the button above to file a new report.</p>
        </div>
      ) : null}
    </div>
  )
}
