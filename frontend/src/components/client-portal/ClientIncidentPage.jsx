import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch, apiUpload } from '../../lib/apiClient.js'
import { INCIDENT_STATUS_META, isOpenIncidentStatus, PRIORITY_META } from '../../lib/incidentCatalog.js'
import { IncidentDetailPanel } from '../support/IncidentDetailPanel.jsx'
import { IncidentReportForm } from '../support/IncidentReportForm.jsx'
import '../support/support-tickets.css'

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

export function ClientIncidentPage({ cases = [] }) {
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
      const key = c.id
      if (key == null || seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [cases])

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
      setExpandedDetail(await apiFetch(`/api/v1/parent/incidents/${inc.id}`))
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
      if (!body.case_id) {
        setFormError('Please select which child this incident relates to.')
        return
      }
      const created = await apiFetch('/api/v1/parent/incidents', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (files?.length) {
        const fd = new FormData()
        files.forEach((f) => fd.append('files', f))
        if (attachment_note) fd.append('note', attachment_note)
        try {
          await apiUpload(`/api/v1/parent/incidents/${created.id}/attachments`, fd)
        } catch (uploadErr) {
          setFormSuccess(created.confirmation || 'Your report has been submitted.')
          setFormError(
            uploadErr.message ||
              `Report ${created.ticket_code || ''} was saved, but we could not upload your file(s). Try adding them from the incident thread.`,
          )
          setShowForm(false)
          setExpandedId(created.id)
          setIncidents((prev) => {
            const exists = prev.some((row) => row.id === created.id)
            if (exists) return prev
            return [{ ...created }, ...prev]
          })
          await loadIncidents()
          try {
            setExpandedDetail(await apiFetch(`/api/v1/parent/incidents/${created.id}`))
          } catch {
            setExpandedDetail(null)
          }
          return
        }
      }
      setFormSuccess(created.confirmation || 'Your report has been submitted.')
      setShowForm(false)
      setExpandedId(created.id)
      setIncidents((prev) => {
        const exists = prev.some((row) => row.id === created.id)
        if (exists) {
          return prev.map((row) => (row.id === created.id ? { ...row, ...created } : row))
        }
        return [{ ...created }, ...prev]
      })
      await loadIncidents()
      setExpandedDetail(await apiFetch(`/api/v1/parent/incidents/${created.id}`))
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
                <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', fontWeight: 700, color: '#3730a3' }}>
                  {inc.ticket_code}
                </span>
              ) : null}
              <StatusPill status={inc.status} />
              {inc.priority ? <PriorityPill priority={inc.priority} /> : null}
              <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: '#94a3b8' }}>
                {new Date(inc.created_at).toLocaleDateString()}
              </span>
            </div>
            <p style={{ fontWeight: 600, margin: '0 0 2px', fontSize: '0.9rem' }}>{inc.title}</p>
            {inc.case_code || inc.child_name ? (
              <p style={{ margin: 0, fontSize: '0.78rem', color: '#64748b' }}>
                {[inc.case_code, inc.child_name].filter(Boolean).join(' · ')}
              </p>
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
          <h2 style={{ margin: 0 }}>Incident Reports</h2>
          <button
            type="button"
            onClick={() => { setShowForm((s) => !s); setFormError(''); setFormSuccess('') }}
            style={{ background: showForm ? '#f1f5f9' : '#ef4444', color: showForm ? '#475569' : '#fff', border: 'none', borderRadius: 10, padding: '8px 16px', fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer' }}
          >
            {showForm ? 'Cancel' : '+ Report an incident'}
          </button>
        </div>
        <p className="parent-support__hint">
          Report concerns about your child&apos;s care. You will receive a ticket reference and updates in this thread.
        </p>

        {showForm ? (
          <div style={{ marginTop: 12 }}>
            <IncidentReportForm
              cases={caseOptions.map((c) => ({
                id: c.id,
                child_name: c.childName,
                case_code: c.caseId,
                service_type: c.serviceType,
                product_module: c.productModule,
              }))}
              caseRequired={caseOptions.length > 0}
              hideServiceType
              onSubmit={submitReport}
              submitting={submitting}
              error={formError}
            />
          </div>
        ) : null}

        {formSuccess ? <p style={{ color: '#15803d', fontSize: '0.875rem', marginTop: 12 }}>{formSuccess}</p> : null}
      </section>

      <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Active ({openIncidents.length})</h2>
      {loading ? (
        <p style={{ color: '#94a3b8' }}>Loading…</p>
      ) : openIncidents.length === 0 ? (
        <p style={{ color: '#94a3b8' }}>No active reports.</p>
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
