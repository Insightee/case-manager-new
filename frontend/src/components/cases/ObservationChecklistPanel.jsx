import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'

function previewText(text, maxLen = 180) {
  const t = (text || '').trim()
  if (!t) return '—'
  if (t.length <= maxLen) return t
  return `${t.slice(0, maxLen)}…`
}

function ObservationSummaryCard({ checklist, onExpand, expanded }) {
  const previewKeys = ['summary_recommendations', 'referral_context', 'social_communication']
  const sections = checklist.sections || []
  const previewSections = [
    ...previewKeys.map((k) => sections.find((s) => s.key === k)).filter(Boolean),
    ...sections.filter((s) => !previewKeys.includes(s.key) && (checklist.responses?.[s.key] || '').trim()),
  ].slice(0, expanded ? sections.length : 3)

  return (
    <div
      className="ic-observation-summary"
      style={{
        marginTop: 16,
        padding: 16,
        borderRadius: 12,
        border: '1px solid #e2e8f0',
        background: '#f8fafc',
      }}
    >
      {checklist.submitted_at ? (
        <p style={{ margin: '0 0 12px', fontSize: '0.8rem', color: '#64748b' }}>
          Submitted {formatDisplayDate(checklist.submitted_at?.slice(0, 10))}
          {checklist.reviewed_at ? ` · Reviewed ${formatDisplayDate(checklist.reviewed_at?.slice(0, 10))}` : ''}
        </p>
      ) : null}

      {previewSections.map((section) => (
        <div key={section.key} style={{ marginBottom: 12 }}>
          <p style={{ margin: '0 0 4px', fontWeight: 600, fontSize: '0.85rem' }}>{section.label}</p>
          <p style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.9rem', color: '#334155' }}>
            {expanded
              ? checklist.responses?.[section.key] || '—'
              : previewText(checklist.responses?.[section.key])}
          </p>
        </div>
      ))}

      {sections.length > 3 ? (
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          onClick={onExpand}
          style={{ marginTop: 4 }}
        >
          {expanded ? 'Show less' : 'View full checklist'}
        </button>
      ) : null}

      {checklist.observation_report_id ? (
        <p style={{ margin: '12px 0 0', fontSize: '0.85rem', color: '#64748b' }}>
          Observation report #{checklist.observation_report_id} is on file for this case.
        </p>
      ) : null}
    </div>
  )
}

export function ObservationChecklistPanel({ caseId }) {
  const [checklist, setChecklist] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [summaryExpanded, setSummaryExpanded] = useState(false)

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
      setSummaryExpanded(false)
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

  const showEditForm = checklist.can_edit

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
          Due {formatDisplayDate(checklist.due_at?.slice?.(0, 10) || checklist.due_at)}
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

      {showEditForm ? (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
            {(checklist.sections || []).map((section) => (
              <div key={section.key}>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: 6, fontSize: '0.9rem' }}>
                  {section.label}
                </label>
                <textarea
                  value={checklist.responses?.[section.key] || ''}
                  onChange={(e) => setResponse(section.key, e.target.value)}
                  rows={4}
                  style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #e2e8f0' }}
                  placeholder="Enter observations for this section…"
                />
              </div>
            ))}
          </div>
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
        </>
      ) : (
        <ObservationSummaryCard
          checklist={checklist}
          expanded={summaryExpanded}
          onExpand={() => setSummaryExpanded((v) => !v)}
        />
      )}
    </section>
  )
}
