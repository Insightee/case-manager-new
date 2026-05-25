import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function ObservationChecklistPanel({ caseId }) {
  const [checklist, setChecklist] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/observation-checklist`)
      setChecklist(data)
    } catch (err) {
      setError(err.message || 'Could not load observation checklist')
      setChecklist(null)
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  function setResponse(key, value) {
    setChecklist((prev) =>
      prev ? { ...prev, responses: { ...prev.responses, [key]: value } } : prev,
    )
  }

  async function saveDraft() {
    if (!checklist?.can_edit) return
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/observation-checklist`, {
        method: 'PUT',
        body: JSON.stringify({ responses: checklist.responses, sync_clinical_profile: true }),
      })
      setChecklist(data)
      setMessage('Draft saved.')
    } catch (err) {
      setError(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function submit() {
    setSaving(true)
    setError('')
    try {
      await saveDraft()
      const data = await apiFetch(`/api/v1/cases/${caseId}/observation-checklist/submit`, {
        method: 'POST',
      })
      setChecklist(data)
      setMessage('Submitted to your case manager for review.')
    } catch (err) {
      setError(err.message || 'Submit failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-sm text-slate-500">Loading observation checklist…</p>
  if (!checklist) {
    return error ? (
      <p role="alert" style={{ color: '#b91c1c' }}>
        {error}
      </p>
    ) : null
  }

  const statusLabel = {
    DRAFT: 'Draft',
    SUBMITTED: 'Awaiting case manager review',
    APPROVED: 'Approved — shared with parent when published',
    REJECTED: 'Changes requested',
  }[checklist.status] || checklist.status

  return (
    <section className="ic-case-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <h3 style={{ margin: '0 0 4px' }}>Observation checklist</h3>
          <p className="ic-case-panel__hint" style={{ margin: 0 }}>
            Complete all sections when due. Shadow support: within 30 days of case start. Homecare: after 3 completed
            sessions.
          </p>
        </div>
        <span
          className={`status ${checklist.is_overdue ? 'warning' : checklist.status === 'APPROVED' ? 'completed' : 'pending'}`}
        >
          {statusLabel}
        </span>
      </div>

      {checklist.due_at ? (
        <p style={{ fontSize: '0.8rem', color: checklist.is_overdue ? '#b45309' : '#64748b', margin: '8px 0' }}>
          Due {checklist.due_at}
          {checklist.is_overdue ? ' (overdue)' : checklist.is_due ? ' (due now)' : ''}
        </p>
      ) : null}

      {error ? (
        <p role="alert" style={{ color: '#b91c1c', marginTop: 8 }}>
          {error}
        </p>
      ) : null}
      {message ? (
        <p style={{ marginTop: 8, color: '#047857', fontSize: '0.875rem' }}>
          {message}
        </p>
      ) : null}

      {checklist.reviewer_comment && checklist.status === 'REJECTED' ? (
        <p style={{ marginTop: 8, padding: 10, background: '#fff7ed', borderRadius: 8, fontSize: '0.875rem' }}>
          <strong>Case manager:</strong> {checklist.reviewer_comment}
        </p>
      ) : null}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
        {(checklist.sections || []).map((section) => (
          <div key={section.key}>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 6, fontSize: '0.9rem' }}>
              {section.label}
            </label>
            <textarea
              value={checklist.responses?.[section.key] || ''}
              onChange={(e) => setResponse(section.key, e.target.value)}
              disabled={!checklist.can_edit}
              rows={4}
              style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e2e8f0' }}
              placeholder={checklist.can_edit ? 'Enter observations for this section…' : ''}
            />
          </div>
        ))}
      </div>

      {checklist.can_edit ? (
        <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
          <button type="button" className="admin-btn admin-btn--secondary" disabled={saving} onClick={saveDraft}>
            Save draft
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--primary"
            disabled={saving || !checklist.can_submit}
            onClick={submit}
          >
            Submit for review
          </button>
        </div>
      ) : checklist.observation_report_id ? (
        <p style={{ marginTop: 12, fontSize: '0.85rem', color: '#64748b' }}>
          Observation report #{checklist.observation_report_id} is on file for this case.
        </p>
      ) : null}
    </section>
  )
}
