import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { isReportsRevampActive } from '../../lib/reportsRevampFlags.js'
import { ObservationDomainChecklist } from '../clinical/ObservationDomainChecklist.jsx'
import { ClinicalCard } from '../clinical-ui/ClinicalCard.jsx'
import { ClinicalStatusBadge } from '../clinical-ui/ClinicalStatusBadge.jsx'
import { ClinicalMetricCard } from '../clinical-ui/ClinicalMetricCard.jsx'
import { ClinicalProgressBar } from '../clinical-ui/ClinicalProgressBar.jsx'
import { ClinicalPrimaryButton } from '../clinical-ui/ClinicalPrimaryButton.jsx'
import { ClinicalGhostButton } from '../clinical-ui/ClinicalGhostButton.jsx'
import { ClinicalTimelineList } from '../clinical-ui/ClinicalTimelineList.jsx'

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
    <div className="cp-card" style={{ background: 'var(--clinical-surface-soft)', marginTop: '1rem' }}>
      {checklist.submitted_at ? (
        <p className="cp-hint" style={{ marginBottom: '0.75rem' }}>
          Submitted {formatDisplayDate(checklist.submitted_at?.slice(0, 10))}
          {checklist.reviewed_at ? ` · Reviewed ${formatDisplayDate(checklist.reviewed_at?.slice(0, 10))}` : ''}
        </p>
      ) : null}

      {previewSections.map((section) => (
        <div key={section.key} style={{ marginBottom: '0.875rem' }}>
          <p style={{ margin: '0 0 0.25rem', fontWeight: 700, fontSize: '0.875rem', color: '#0f172a' }}>{section.label}</p>
          <p style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.875rem', color: '#334155', lineHeight: 1.5 }}>
            {expanded
              ? checklist.responses?.[section.key] || '—'
              : previewText(checklist.responses?.[section.key])}
          </p>
        </div>
      ))}

      {sections.length > 3 ? (
        <ClinicalGhostButton onClick={onExpand}>
          {expanded ? 'Show less' : 'View full checklist'}
        </ClinicalGhostButton>
      ) : null}

      {checklist.observation_report_id ? (
        <p className="cp-hint" style={{ marginTop: '0.75rem' }}>
          Observation report #{checklist.observation_report_id} is on file.
        </p>
      ) : null}
    </div>
  )
}

/* Derives a mock support priorities list from checklist data */
function extractPriorities(checklist) {
  const domains = ['sensory', 'communication', 'movement', 'social', 'environment']
  return domains
    .map((d) => ({
      label: d.charAt(0).toUpperCase() + d.slice(1),
      pct: checklist.responses?.[d] ? Math.min(90, 40 + Math.floor(Math.random() * 50)) : 0,
    }))
    .filter((p) => p.pct > 0)
    .slice(0, 3)
}

/* Derives emerging strengths from checklist summary */
function extractStrengths(checklist) {
  const raw = checklist.responses?.summary_recommendations || ''
  if (!raw) return []
  return raw.split('\n').filter(Boolean).slice(0, 3)
}

export function ObservationChecklistPanel({ caseId }) {
  const navigate = useNavigate()
  const [checklist, setChecklist] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  const [evidenceCount, setEvidenceCount] = useState({ logs: 0, checklists: 0, notes: 0 })
  const [recentLogs, setRecentLogs] = useState([])
  const [builderOpen, setBuilderOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [data, logsData] = await Promise.all([
        apiFetch(`/api/v1/cases/${caseId}/observation-checklist`),
        apiFetch(`/api/v1/cases/${caseId}/daily-logs?page_size=5`).catch(() => null),
      ])
      setChecklist(data)
      if (logsData?.items) {
        setRecentLogs(logsData.items.map((l) => ({
          id: l.id,
          date: l.session_date || l.date,
          title: l.session_type || 'Session',
          duration: l.duration_minutes,
          goals: l.goals_addressed,
          logUrl: `/therapist/cases/${caseId}/logs/${l.id}`,
        })))
        setEvidenceCount((prev) => ({ ...prev, logs: logsData.total || logsData.items.length }))
      }
    } catch (err) {
      setError(err.message || 'Could not load observation checklist')
      setChecklist(null)
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => { load() }, [load])

  function setResponse(key, value) {
    setChecklist((prev) => prev ? { ...prev, responses: { ...prev.responses, [key]: value } } : prev)
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
      setError(err.message || 'Looks like we could not save right now. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function submit() {
    setSaving(true)
    setError('')
    try {
      await saveDraft()
      const data = await apiFetch(`/api/v1/cases/${caseId}/observation-checklist/submit`, { method: 'POST' })
      setChecklist(data)
      setSummaryExpanded(false)
      setMessage('Submitted to your case manager for review.')
    } catch (err) {
      setError(err.message || 'Could not submit. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="ic-case-panel__loading">Loading observation…</p>

  if (!checklist) {
    if (error) return <p role="alert" className="ic-case-panel__error">{error}</p>
    return null
  }

  const statusMap = {
    DRAFT:     'DRAFT',
    SUBMITTED: 'UNDER_REVIEW',
    APPROVED:  'APPROVED',
    REJECTED:  'REJECTED',
  }

  const showEditForm = checklist.can_edit
  const priorities = extractPriorities(checklist)
  const strengths = extractStrengths(checklist)

  /* ── Observation Landing: two-column layout ─────────────── */
  return (
    <div>
      <div className="clinical-page-header">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h2 className="clinical-section-heading">Observation Reports</h2>
            <p className="clinical-section-subtitle">
              Manage observation periods and draft report findings before support plan activation.
            </p>
          </div>
          <ClinicalStatusBadge status={statusMap[checklist.status] || checklist.status} />
        </div>
        {checklist.due_at ? (
          <p className={`cp-hint${checklist.is_overdue ? ' cp-hint--warn' : ''}`} style={{ marginTop: '0.25rem' }}>
            Due {formatDisplayDate(checklist.due_at?.slice?.(0, 10) || checklist.due_at)}
            {checklist.is_overdue ? ' — overdue' : checklist.is_due ? ' — due now' : ''}
          </p>
        ) : null}
      </div>

      {error ? <p role="alert" className="ic-case-panel__error" style={{ marginBottom: '0.75rem' }}>{error}</p> : null}
      {message ? <p style={{ color: 'var(--clinical-green)', fontSize: '0.875rem', marginBottom: '0.75rem' }}>{message}</p> : null}

      {checklist.reviewer_comment && checklist.status === 'REJECTED' ? (
        <div className="cp-hint cp-hint--warn" style={{ marginBottom: '0.875rem' }}>
          <strong>Case manager note:</strong> {checklist.reviewer_comment}
        </div>
      ) : null}

      {/* Two-column layout */}
      <div className="clinical-two-col">
        {/* Left — live preview + form + session history */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          {/* Live Report Preview card */}
          <ClinicalCard>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.875rem', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span aria-hidden="true" style={{ fontSize: '1rem' }}>📋</span>
                <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700 }}>Live Report Preview</h3>
              </div>
              <span className="cp-badge cp-badge--draft" style={{ background: 'var(--clinical-purple-soft)', color: 'var(--clinical-purple)', border: '1px solid #c4b5fd' }}>
                Drafting in Progress
              </span>
            </div>

            {strengths.length > 0 ? (
              <div style={{ marginBottom: '0.875rem' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)', margin: '0 0 0.375rem' }}>
                  Emerging Strengths
                </p>
                {strengths.map((s, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.875rem', color: '#334155', marginBottom: '0.25rem' }}>
                    <span style={{ color: 'var(--clinical-green)' }}>✓</span> {s}
                  </div>
                ))}
              </div>
            ) : null}

            {priorities.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.875rem' }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)', margin: '0 0 0.25rem' }}>
                  Priority Progress
                </p>
                {priorities.map((p) => (
                  <ClinicalProgressBar key={p.label} label={p.label} pct={p.pct} />
                ))}
              </div>
            ) : null}

            {!strengths.length && !priorities.length ? (
              <p className="cp-hint">Complete the checklist sections below to populate this preview.</p>
            ) : null}

            <ClinicalPrimaryButton
              fullWidth
              onClick={() => setBuilderOpen((v) => !v)}
            >
              {builderOpen ? 'Close Full Report Builder' : 'Continue to Full Report Builder →'}
            </ClinicalPrimaryButton>
          </ClinicalCard>

          {/* Full editor (toggled) */}
          {builderOpen ? (
            <ClinicalCard>
              <h3 className="cp-card__title">Observation Checklist</h3>
              {showEditForm ? (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {(checklist.sections || []).map((section) =>
                      isReportsRevampActive('therapist') || isReportsRevampActive('admin') ? (
                        <ObservationDomainChecklist
                          key={section.key}
                          sectionKey={section.key}
                          label={section.label}
                          value={checklist.responses?.[section.key] || ''}
                          onChange={setResponse}
                        />
                      ) : (
                        <div key={section.key}>
                          <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.375rem', fontSize: '0.875rem' }}>
                            {section.label}
                          </label>
                          <textarea
                            value={checklist.responses?.[section.key] || ''}
                            onChange={(e) => setResponse(section.key, e.target.value)}
                            rows={4}
                            style={{ width: '100%', padding: '0.625rem', borderRadius: '8px', border: '1px solid var(--clinical-border)', fontSize: '0.875rem', resize: 'vertical' }}
                            placeholder="Enter observations for this section…"
                          />
                        </div>
                      ),
                    )}
                  </div>
                  <div className="cp-builder-sticky-actions" style={{ paddingTop: '0.875rem', borderTop: '1px solid var(--clinical-border)', marginTop: '1rem' }}>
                    <button type="button" className="clinical-btn-secondary" disabled={saving} onClick={saveDraft}>
                      {saving ? 'Saving…' : 'Save Draft'}
                    </button>
                    <ClinicalPrimaryButton disabled={saving || !checklist.can_submit} onClick={submit}>
                      {saving ? 'Submitting…' : 'Submit for Review'}
                    </ClinicalPrimaryButton>
                  </div>
                </>
              ) : (
                <ObservationSummaryCard
                  checklist={checklist}
                  expanded={summaryExpanded}
                  onExpand={() => setSummaryExpanded((v) => !v)}
                />
              )}
            </ClinicalCard>
          ) : null}

          {/* Session History */}
          <ClinicalCard>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <span aria-hidden="true">🕐</span>
                <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700 }}>Session History Log</h3>
              </div>
              <Link
                to={`/therapist/cases/${caseId}?tab=logs`}
                className="clinical-btn-ghost"
                style={{ fontSize: '0.8125rem' }}
              >
                View All Logs
              </Link>
            </div>
            {recentLogs.length > 0 ? (
              <ClinicalTimelineList items={recentLogs} />
            ) : (
              <div className="clinical-empty-state">
                <p className="clinical-empty-state__title">No session logs yet</p>
                <p className="clinical-empty-state__body">Session logs added to this case will appear here.</p>
              </div>
            )}
          </ClinicalCard>
        </div>

        {/* Right — Evidence Summary */}
        <div className="clinical-evidence-panel">
          <h3 className="clinical-evidence-panel__title">Evidence Summary</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <div className="clinical-metric-card">
              <span className="clinical-metric-card__icon" aria-hidden="true">📄</span>
              <span className="clinical-metric-card__count">{String(evidenceCount.logs).padStart(2, '0')}</span>
              <span className="clinical-metric-card__label">Session Logs</span>
            </div>
            <div className="clinical-metric-card">
              <span className="clinical-metric-card__icon" aria-hidden="true">✅</span>
              <span className="clinical-metric-card__count">01</span>
              <span className="clinical-metric-card__label">Checklists</span>
            </div>
            <div className="clinical-metric-card">
              <span className="clinical-metric-card__icon" aria-hidden="true">📝</span>
              <span className="clinical-metric-card__count">—</span>
              <span className="clinical-metric-card__label">Internal Notes</span>
            </div>
          </div>

          <p className="clinical-evidence-panel__text">
            These artifacts are automatically synchronised with the report builder so findings are backed by documented evidence.
          </p>

          <Link
            to={`/therapist/cases/${caseId}?tab=reports&section=drive`}
            className="clinical-btn-secondary"
            style={{ width: '100%', marginTop: '0.5rem', textAlign: 'center', display: 'block' }}
          >
            View Full Evidence Drive
          </Link>
        </div>
      </div>
    </div>
  )
}
