import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch, apiUpload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { INCIDENT_STATUS_META, isOpenIncidentStatus, PRIORITY_META } from '../../lib/incidentCatalog.js'
import { IncidentDetailPanel } from '../support/IncidentDetailPanel.jsx'
import { IncidentReportForm } from '../support/IncidentReportForm.jsx'
import '../support/support-tickets.css'
import '../client-portal/parent-support.css'

function StatusPill({ status }) {
  const m = INCIDENT_STATUS_META[status] || INCIDENT_STATUS_META.REPORTED
  return (
    <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', padding: '3px 8px', borderRadius: 6, background: m.bg, color: m.color }}>
      {m.label}
    </span>
  )
}

function PriorityPill({ priority }) {
  const m = PRIORITY_META[priority] || PRIORITY_META.NORMAL
  return (
    <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: 5, background: m.bg, color: m.color }}>
      {m.label}
    </span>
  )
}

export function TherapistIncidentsPage() {
  const [searchParams] = useSearchParams()
  const initialCaseId = searchParams.get('case_id') || ''
  const [cases, setCases] = useState([])
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [expandedDetail, setExpandedDetail] = useState(null)
  const [showForm, setShowForm] = useState(false)
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
    () => incidents.filter((i) => isOpenIncidentStatus(i.status)),
    [incidents],
  )
  const closedIncidents = useMemo(
    () => incidents.filter((i) => i.status === 'CLOSED'),
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

  async function submitReport(payload) {
    setSubmitting(true)
    setFormError('')
    setFormSuccess('')
    try {
      const { files, attachment_note, ...body } = payload
      const created = await apiFetch('/api/v1/incidents', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (files?.length) {
        const fd = new FormData()
        files.forEach((f) => fd.append('files', f))
        if (attachment_note) fd.append('note', attachment_note)
        await apiUpload(`/api/v1/incidents/${created.id}/attachments`, fd)
      }
      setFormSuccess(created.confirmation || `Incident ${created.ticket_code} submitted.`)
      setShowForm(false)
      setExpandedId(created.id)
      await loadIncidents()
      setExpandedDetail(await apiFetch(`/api/v1/incidents/${created.id}`))
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
              {inc.ticket_code ? (
                <span style={{ fontSize: '0.72rem', fontWeight: 700, fontFamily: 'monospace', color: '#3730a3' }}>
                  {inc.ticket_code}
                </span>
              ) : null}
              <StatusPill status={inc.status} />
              {inc.priority ? <PriorityPill priority={inc.priority} /> : null}
              <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: '#94a3b8' }}>
                {new Date(inc.created_at).toLocaleDateString()}
              </span>
            </div>
            <p style={{ fontWeight: 600, margin: '0 0 2px', fontSize: '0.9rem', color: '#0f172a' }}>{inc.title}</p>
            {inc.child_name ? <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b' }}>{inc.child_name}</p> : null}
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
          Report safety, conduct, or welfare concerns. Your report gets a ticket ID and is routed to the right team.
        </p>

        {showForm ? (
          <div style={{ marginTop: 12 }}>
            <IncidentReportForm
              cases={cases}
              caseRequired
              initialCaseId={initialCaseId}
              hideServiceType={cases.length > 0}
              onSubmit={submitReport}
              submitting={submitting}
              error={formError}
            />
          </div>
        ) : null}

        {formSuccess ? <p style={{ color: '#15803d', fontSize: '0.875rem', marginTop: 12 }}>{formSuccess}</p> : null}
      </section>

      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Active reports ({openIncidents.length})</h2>
      {loading ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>Loading…</p>
      ) : openIncidents.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: 24 }}>No active incident reports.</p>
      ) : (
        openIncidents.map(renderRow)
      )}

      {closedIncidents.length > 0 ? (
        <>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '24px 0 12px' }}>Closed</h2>
          {closedIncidents.map(renderRow)}
        </>
      ) : null}
    </div>
  )
}
