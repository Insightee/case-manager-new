import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { IncidentDetailPanel } from '../support/IncidentDetailPanel.jsx'
import '../support/support-tickets.css'

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

export function ClientIncidentPage({ cases = [] }) {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [expandedDetail, setExpandedDetail] = useState(null)

  // New-report form
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
      const rows = await apiFetch('/api/v1/parent/incidents')
      setIncidents(rows || [])
    } catch {
      setIncidents([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadIncidents()
  }, [loadIncidents])

  const caseOptions = useMemo(() => {
    const seen = new Set()
    return (cases || []).filter((c) => {
      const key = c.caseId || c.id
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [cases])

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
      setExpandedDetail(await apiFetch(`/api/v1/parent/incidents/${inc.id}`))
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
      const created = await apiFetch('/api/v1/parent/incidents', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          case_id: caseId ? Number(caseId) : undefined,
        }),
      })
      setFormSuccess('Your report has been submitted. The team will review and respond.')
      setTitle('')
      setDescription('')
      setCaseId('')
      setShowForm(false)
      await loadIncidents()
      setExpandedId(created.id)
      apiFetch(`/api/v1/parent/incidents/${created.id}`).then(setExpandedDetail).catch(() => {})
    } catch (err) {
      setFormError(err.message || 'Could not submit report')
    } finally {
      setSubmitting(false)
    }
  }

  function renderRow(inc) {
    const isExpanded = expandedId === inc.id
    return (
      <div
        key={inc.id}
        style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, marginBottom: 10, overflow: 'hidden' }}
      >
        <div
          role="button"
          tabIndex={0}
          onClick={() => toggleExpand(inc)}
          onKeyDown={(e) => e.key === 'Enter' && toggleExpand(inc)}
          style={{ padding: '14px 16px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
              <StatusPill status={inc.status} />
              {inc.case_code ? (
                <span style={{ fontSize: '0.72rem', fontWeight: 700, background: '#eef2ff', color: '#3730a3', border: '1px solid #c7d2fe', borderRadius: 6, padding: '2px 7px', fontFamily: 'monospace' }}>
                  {inc.case_code}
                </span>
              ) : null}
            </div>
            <p style={{ fontWeight: 600, margin: '0 0 2px', fontSize: '0.9rem', color: '#0f172a' }}>{inc.title}</p>
            <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b' }}>
              {inc.child_name || ''}
              {inc.child_name ? ' · ' : ''}
              {new Date(inc.created_at).toLocaleDateString()}
            </p>
          </div>
          <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>{isExpanded ? '▲' : '▼'}</span>
        </div>

        {isExpanded ? (
          <div style={{ borderTop: '1px solid #f1f5f9', padding: '0 16px 16px', background: '#fafafa' }}>
            {expandedDetail?.id === inc.id ? (
              <IncidentDetailPanel
                incident={expandedDetail}
                onUpdated={onDetailUpdated}
                apiBase="/api/v1/parent/incidents"
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
      <section className="parent-support__form-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Incident Reporting</h2>
          <button
            type="button"
            onClick={() => { setShowForm((s) => !s); setFormError(''); setFormSuccess('') }}
            style={{ background: '#ef4444', color: '#fff', border: 'none', borderRadius: 10, padding: '8px 16px', fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer' }}
          >
            {showForm ? 'Cancel' : '+ Report an incident'}
          </button>
        </div>
        <p className="parent-support__hint">
          Use this to report any concern about your child's safety, conduct, or wellbeing. The care team will review and respond.
        </p>

        {showForm ? (
          <form onSubmit={submit}>
            {caseOptions.length > 0 ? (
              <label className="parent-support__field">
                Child (optional)
                <select value={caseId} onChange={(e) => setCaseId(e.target.value)}>
                  <option value="">Not linked to a specific child</option>
                  {caseOptions.map((c) => (
                    <option key={c.id || c.caseId} value={c.id || c.caseId}>
                      {c.childName} · {c.caseId}
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
                placeholder="Brief summary"
              />
            </label>
            <label className="parent-support__field">
              Description
              <textarea
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what happened and any concerns you have…"
              />
            </label>
            {formError ? <p style={{ color: '#b91c1c', fontSize: '0.8rem', marginBottom: 8 }}>{formError}</p> : null}
            <button
              type="submit"
              disabled={submitting}
              className="parent-support__submit"
              style={{ background: '#ef4444', borderColor: '#ef4444' }}
            >
              {submitting ? 'Submitting…' : 'Submit report'}
            </button>
          </form>
        ) : null}

        {formSuccess ? (
          <p style={{ color: '#15803d', fontSize: '0.875rem', marginTop: 12 }}>{formSuccess}</p>
        ) : null}
      </section>

      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>
        Active reports ({openIncidents.length})
      </h2>
      {loading ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>Loading…</p>
      ) : openIncidents.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>No active reports.</p>
      ) : (
        openIncidents.map(renderRow)
      )}

      {closedIncidents.length > 0 ? (
        <>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '24px 0 12px' }}>Closed / resolved</h2>
          {closedIncidents.map(renderRow)}
        </>
      ) : null}
    </div>
  )
}
