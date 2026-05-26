import { useCallback, useEffect, useState } from 'react'
import { apiDownload, apiFetch, apiUpload } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import {
  emptySections,
  IEP_TAB_ORDER,
  LEARNING_STYLES,
  normalizeSections,
  PERFORMANCE_DOMAINS,
  validateSectionsForShare,
} from './iepBuilderDefaults.js'
import './admin-iep-builder.css'

const TABS = [
  { id: 'header', label: 'Header' },
  { id: 'clinical', label: 'Clinical' },
  { id: 'goals', label: 'Goals' },
  { id: 'verification', label: 'Verification' },
]

function Field({ label, children, hint }) {
  return (
    <div className="iep-builder__field">
      <label>{label}</label>
      {children}
      {hint ? <p className="iep-builder__hint">{hint}</p> : null}
    </div>
  )
}

export function IepBuilderPanel({ caseId }) {
  const { user } = useAuth()
  const { canEditIep } = useModuleWrite()
  const [plan, setPlan] = useState(null)
  const [versionHistory, setVersionHistory] = useState([])
  const [sections, setSections] = useState(emptySections)
  const [tab, setTab] = useState('header')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [previewHtml, setPreviewHtml] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [shareFlowOpen, setShareFlowOpen] = useState(false)
  const [shareStep, setShareStep] = useState(0)
  const [previewAcknowledged, setPreviewAcknowledged] = useState(false)
  const [attachmentNames, setAttachmentNames] = useState({})
  const [auditItems, setAuditItems] = useState([])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [data, versions, audit] = await Promise.all([
        apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan`),
        apiFetch(`/api/v1/admin/cases/${caseId}/iep-plans`).catch(() => []),
        apiFetch(`/api/v1/admin/audit?case_id=${caseId}&entity_type=iep_plan&limit=15`).catch(() => ({
          items: [],
        })),
      ])
      setPlan(data)
      setSections(normalizeSections(data.sections, data.case_context))
      setVersionHistory(Array.isArray(versions) ? versions : [])
      setAuditItems(audit?.items || [])
    } catch (err) {
      setError(err.message || 'Could not load IEP plan')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!plan?.case_context) return
    setSections((s) => normalizeSections(s, plan.case_context))
  }, [plan?.id, plan?.case_context])

  const productModule = plan?.case_context?.product_module || 'homecare'
  const canEdit = Boolean(plan?.can_edit && canEditIep(productModule))
  const tabIndex = IEP_TAB_ORDER.indexOf(tab)

  function patch(path, value) {
    setSections((s) => {
      const next = JSON.parse(JSON.stringify(s))
      const keys = path.split('.')
      let cur = next
      for (let i = 0; i < keys.length - 1; i += 1) cur = cur[keys[i]]
      cur[keys[keys.length - 1]] = value
      return next
    })
  }

  function patchEnv(idx, field, value) {
    setSections((s) => {
      const rows = [...(s.learning_environments || [])]
      rows[idx] = { ...rows[idx], [field]: value }
      return { ...s, learning_environments: rows }
    })
  }

  function patchPerf(domain, notes) {
    setSections((s) => ({
      ...s,
      current_performance: (s.current_performance || []).map((p) =>
        p.domain === domain ? { ...p, notes } : p
      ),
    }))
  }

  function toggleStyle(key) {
    setSections((s) => {
      const styles = new Set(s.learning_style?.styles || [])
      if (styles.has(key)) styles.delete(key)
      else styles.add(key)
      return { ...s, learning_style: { ...s.learning_style, styles: [...styles] } }
    })
  }

  function goNext() {
    if (tabIndex < IEP_TAB_ORDER.length - 1) {
      setTab(IEP_TAB_ORDER[tabIndex + 1])
    }
  }

  function goBack() {
    if (tabIndex > 0) {
      setTab(IEP_TAB_ORDER[tabIndex - 1])
    }
  }

  async function save() {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan`, {
        method: 'PUT',
        body: JSON.stringify({ sections, version: plan?.version }),
      })
      setPlan(data)
      setSections(normalizeSections(data.sections, data.case_context))
      setMessage('IEP draft saved.')
    } catch (err) {
      setError(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function openPreview() {
    setSaving(true)
    setError('')
    try {
      if (canEdit) await save()
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan/preview`)
      setPreviewHtml(data.html || '')
      setPreviewOpen(true)
    } catch (err) {
      setError(err.message || 'Preview failed')
    } finally {
      setSaving(false)
    }
  }

  async function downloadPdf() {
    setSaving(true)
    try {
      if (canEdit) await save()
      await apiDownload(
        `/api/v1/admin/cases/${caseId}/iep-plan/export/pdf`,
        `IEP_${plan?.version || 'draft'}.pdf`
      )
    } catch (err) {
      setError(err.message || 'PDF download failed')
    } finally {
      setSaving(false)
    }
  }

  async function startShareFlow() {
    const errs = validateSectionsForShare(sections)
    if (errs.length) {
      setError(errs.join(' '))
      setTab('verification')
      return
    }
    setShareFlowOpen(true)
    setShareStep(0)
    setPreviewAcknowledged(false)
    await openPreviewForShare()
  }

  async function openPreviewForShare() {
    setSaving(true)
    setError('')
    try {
      if (canEdit) await save()
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan/preview`)
      setPreviewHtml(data.html || '')
    } catch (err) {
      setError(err.message || 'Preview failed')
    } finally {
      setSaving(false)
    }
  }

  async function shareWithParent() {
    setSaving(true)
    setError('')
    try {
      if (canEdit) await save()
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan/share-with-parent`, {
        method: 'POST',
      })
      setPlan(data)
      setShareFlowOpen(false)
      setMessage('IEP shared with parent for acknowledgement.')
      await load()
    } catch (err) {
      setError(err.message || 'Share failed')
    } finally {
      setSaving(false)
    }
  }

  async function createRevision() {
    setSaving(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan/new-version`, {
        method: 'POST',
      })
      setPlan(data)
      setSections(normalizeSections(data.sections, data.case_context))
      setTab('header')
      setMessage(`Revision ${data.version} created. You can edit and share when ready.`)
      await load()
    } catch (err) {
      setError(err.message || 'Could not create revision')
    } finally {
      setSaving(false)
    }
  }

  async function uploadSupplement(file) {
    const fd = new FormData()
    fd.append('case_id', String(caseId))
    fd.append('entity_type', 'iep_plan_supplement')
    fd.append('visibility_status', 'INTERNAL_ONLY')
    fd.append('file', file)
    const res = await apiUpload('/api/v1/attachments', fd)
    const ids = [...(sections.supplementary_attachment_ids || []), res.id]
    setAttachmentNames((m) => ({ ...m, [res.id]: res.file_name }))
    setSections((s) => ({ ...s, supplementary_attachment_ids: ids }))
    return res
  }

  async function removeSupplement(id) {
    setSections((s) => ({
      ...s,
      supplementary_attachment_ids: (s.supplementary_attachment_ids || []).filter((x) => x !== id),
    }))
  }

  async function resolveSuggestions() {
    setSaving(true)
    try {
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan/suggestions/resolve`, {
        method: 'POST',
      })
      setPlan(data)
      setSections(normalizeSections(data.sections, data.case_context))
      setMessage('Suggestions marked resolved.')
    } catch (err) {
      setError(err.message || 'Could not resolve suggestions')
    } finally {
      setSaving(false)
    }
  }

  async function approvePlan() {
    setSaving(true)
    try {
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan/approve`, { method: 'POST' })
      setPlan(data)
      setMessage('IEP marked approved.')
      await load()
    } catch (err) {
      setError(err.message || 'Approve failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-sm text-slate-500">Loading IEP builder…</p>

  const h = sections.header
  const v = sections.verification
  const openSuggestions = (plan?.suggestions || []).filter((s) => !s.resolved_at)
  const suppIds = sections.supplementary_attachment_ids || []

  return (
    <section className="card iep-builder">
      <div className="iep-builder__toolbar">
        <div>
          <h3 style={{ margin: 0 }}>IEP document builder</h3>
          {plan ? (
            <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '4px 0 0' }}>
              Version {plan.version} · {plan.status.replace(/_/g, ' ')}
              {plan.status === 'INTERNAL_REVIEW' ? ' · awaiting CM review' : ''}
            </p>
          ) : null}
        </div>
        <div className="iep-builder__tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`iep-builder__tab${tab === t.id ? ' is-active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {versionHistory.length > 1 ? (
        <div className="iep-builder__versions">
          <span className="iep-builder__versions-label">Versions:</span>
          {versionHistory.map((ver) => (
            <span key={ver.id} className="iep-builder__version-chip">
              {ver.version} ({ver.status.replace(/_/g, ' ')})
            </span>
          ))}
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="iep-builder__alert iep-builder__alert--error">
          {error}
        </p>
      ) : null}
      {message ? <p className="iep-builder__alert iep-builder__alert--ok">{message}</p> : null}

      {!canEdit && plan?.can_create_revision ? (
        <div className="iep-builder__banner">
          <p>This version was shared with the parent. Create a new revision to make changes.</p>
          <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={createRevision}>
            Create new revision
          </button>
        </div>
      ) : null}

      {tab === 'header' ? (
        <div className="iep-builder__panel iep-builder__grid-2">
          <Field label="Child name">
            <input value={h.child_name} disabled={!canEdit} onChange={(e) => patch('header.child_name', e.target.value)} />
          </Field>
          <Field label="Age">
            <input value={h.age_label} disabled={!canEdit} onChange={(e) => patch('header.age_label', e.target.value)} />
          </Field>
          <Field label="Diagnosis">
            <input value={h.diagnosis} disabled={!canEdit} onChange={(e) => patch('header.diagnosis', e.target.value)} />
          </Field>
          <Field label="Service provided">
            <input value={h.service_provided} disabled={!canEdit} onChange={(e) => patch('header.service_provided', e.target.value)} />
          </Field>
          <Field label="Parents">
            <input value={h.parents_names} disabled={!canEdit} onChange={(e) => patch('header.parents_names', e.target.value)} />
          </Field>
          <Field label="Therapist (header)">
            <input value={h.therapist_name} disabled={!canEdit} onChange={(e) => patch('header.therapist_name', e.target.value)} />
          </Field>
          <Field label="School / home">
            <input value={h.school_or_home_name} disabled={!canEdit} onChange={(e) => patch('header.school_or_home_name', e.target.value)} />
          </Field>
          <Field label="Class / grade">
            <input value={h.class_grade} disabled={!canEdit} onChange={(e) => patch('header.class_grade', e.target.value)} />
          </Field>
          <Field label="Evaluation date">
            <input type="date" value={h.date_of_evaluation || ''} disabled={!canEdit} onChange={(e) => patch('header.date_of_evaluation', e.target.value)} />
          </Field>
          <Field label="IEP meeting date">
            <input type="date" value={h.date_of_iep_meeting || ''} disabled={!canEdit} onChange={(e) => patch('header.date_of_iep_meeting', e.target.value)} />
          </Field>
          <Field label="Review date">
            <input type="date" value={h.review_date || ''} disabled={!canEdit} onChange={(e) => patch('header.review_date', e.target.value)} />
          </Field>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="About the child">
              <textarea rows={4} value={h.about_child_brief} disabled={!canEdit} onChange={(e) => patch('header.about_child_brief', e.target.value)} />
            </Field>
          </div>
        </div>
      ) : null}

      {tab === 'clinical' ? (
        <div className="iep-builder__panel">
          <Field label="Observations">
            <textarea rows={5} value={sections.observations} disabled={!canEdit} onChange={(e) => patch('observations', e.target.value)} />
          </Field>
          <Field label="Challenges">
            <textarea rows={3} value={sections.challenges} disabled={!canEdit} onChange={(e) => patch('challenges', e.target.value)} />
          </Field>
          {PERFORMANCE_DOMAINS.map((d) => {
            const row = (sections.current_performance || []).find((p) => p.domain === d.key) || { notes: '' }
            return (
              <Field key={d.key} label={`Performance — ${d.label}`}>
                <textarea rows={2} value={row.notes} disabled={!canEdit} onChange={(e) => patchPerf(d.key, e.target.value)} />
              </Field>
            )
          })}
          <Field label="Learning style notes">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
              {LEARNING_STYLES.map((ls) => (
                <label key={ls.key} style={{ fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={(sections.learning_style?.styles || []).includes(ls.key)}
                    disabled={!canEdit}
                    onChange={() => toggleStyle(ls.key)}
                  />{' '}
                  {ls.label}
                </label>
              ))}
            </div>
            <textarea rows={2} value={sections.learning_style?.elaboration || ''} disabled={!canEdit} onChange={(e) => patch('learning_style.elaboration', e.target.value)} />
          </Field>
          <Field label="Interventions">
            <textarea rows={3} value={sections.interventions} disabled={!canEdit} onChange={(e) => patch('interventions', e.target.value)} />
          </Field>
          <Field label="Intervention by Insighte">
            <textarea rows={3} value={sections.intervention_by_insighte} disabled={!canEdit} onChange={(e) => patch('intervention_by_insighte', e.target.value)} />
          </Field>
        </div>
      ) : null}

      {tab === 'goals' ? (
        <div className="iep-builder__panel">
          {(sections.learning_environments || []).map((row, idx) => (
            <div key={idx} className="iep-builder__env-row">
              <strong style={{ fontSize: '0.8rem' }}>Environment {idx + 1}</strong>
              <div className="iep-builder__grid-2">
                <Field label="Environment">
                  <input value={row.environment} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'environment', e.target.value)} />
                </Field>
                <Field label="Strengths">
                  <textarea rows={3} className="iep-builder__textarea-lg" value={row.strengths} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'strengths', e.target.value)} />
                </Field>
                <Field label="Goals">
                  <textarea rows={3} className="iep-builder__textarea-lg" value={row.goals} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'goals', e.target.value)} />
                </Field>
                <Field label="Strategies">
                  <textarea rows={4} className="iep-builder__textarea-lg" value={row.strategies} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'strategies', e.target.value)} />
                </Field>
                <Field label="Supports needed">
                  <textarea rows={4} className="iep-builder__textarea-lg" value={row.supports_needed} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'supports_needed', e.target.value)} />
                </Field>
              </div>
            </div>
          ))}
          {canEdit ? (
            <button
              type="button"
              className="admin-btn admin-btn--ghost"
              onClick={() =>
                setSections((s) => ({
                  ...s,
                  learning_environments: [
                    ...(s.learning_environments || []),
                    { environment: '', strengths: '', goals: '', strategies: '', supports_needed: '' },
                  ],
                }))
              }
            >
              Add environment row
            </button>
          ) : null}
          <div className="iep-builder__grid-2">
            <Field label="Talent — strengths">
              <textarea rows={2} value={sections.talent_development?.strengths || ''} disabled={!canEdit} onChange={(e) => patch('talent_development.strengths', e.target.value)} />
            </Field>
            <Field label="Talent — goals">
              <textarea rows={2} value={sections.talent_development?.goals || ''} disabled={!canEdit} onChange={(e) => patch('talent_development.goals', e.target.value)} />
            </Field>
            <Field label="Other needs — areas">
              <textarea rows={2} value={sections.other_areas_of_need?.areas_of_need || ''} disabled={!canEdit} onChange={(e) => patch('other_areas_of_need.areas_of_need', e.target.value)} />
            </Field>
            <Field label="Other needs — goals">
              <textarea rows={2} value={sections.other_areas_of_need?.goals || ''} disabled={!canEdit} onChange={(e) => patch('other_areas_of_need.goals', e.target.value)} />
            </Field>
          </div>
        </div>
      ) : null}

      {tab === 'verification' ? (
        <div className="iep-builder__panel iep-builder__grid-2">
          <label style={{ gridColumn: '1 / -1', display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={!!v.therapist_verified}
              disabled={!canEdit}
              onChange={(e) => patch('verification.therapist_verified', e.target.checked)}
            />
            I verify this document
            {user?.full_name ? ` (${user.full_name})` : ''}
          </label>
          <Field label="Verified by" hint="Set when you check the box above and save.">
            <input value={v.prepared_by_name || ''} disabled readOnly />
          </Field>
          <Field label="Verification date">
            <input value={v.prepared_at || ''} disabled readOnly />
          </Field>
          <Field label="Your role">
            <input value={v.prepared_by_role || user?.roles?.[0] || ''} disabled readOnly />
          </Field>
          <Field label="IEP meeting date">
            <input type="date" value={h.date_of_iep_meeting || ''} disabled={!canEdit} onChange={(e) => patch('header.date_of_iep_meeting', e.target.value)} />
          </Field>
          <Field label="Assigned therapist">
            <input value={v.therapist_name} disabled readOnly />
          </Field>
          <Field label="License no.">
            <input value={v.therapist_license_no} disabled readOnly />
          </Field>
          <Field label="Case manager (on case)">
            <input value={v.case_manager_name} disabled readOnly />
          </Field>
          <Field
            label="Parent acknowledgement"
            hint={v.client_name ? 'Parent has acknowledged.' : 'Filled when the parent acknowledges in their portal.'}
          >
            <input
              value={v.client_name ? `${v.client_name}${v.client_date ? ` · ${v.client_date}` : ''}` : 'Pending parent acknowledgement'}
              disabled
              readOnly
            />
          </Field>
        </div>
      ) : null}

      {(plan?.suggestions || []).length > 0 ? (
        <div className="iep-builder__suggestions">
          <h4 style={{ margin: '0 0 8px' }}>Parent / therapist suggestions</h4>
          {plan.suggestions.map((s) => (
            <div key={s.id} className="iep-builder__suggestion">
              <strong>{s.author_role}</strong> {s.author_name ? `· ${s.author_name}` : ''}
              {s.resolved_at ? ' (resolved)' : ''}
              <p style={{ margin: '4px 0 0' }}>{s.body}</p>
            </div>
          ))}
          {openSuggestions.length > 0 && canEdit ? (
            <button type="button" className="admin-btn admin-btn--ghost" disabled={saving} onClick={resolveSuggestions}>
              Resolve all suggestions
            </button>
          ) : null}
        </div>
      ) : null}

      {auditItems.length > 0 ? (
        <details className="iep-builder__audit">
          <summary>Audit trail</summary>
          <ul>
            {auditItems.map((ev) => (
              <li key={ev.id}>
                <strong>{ev.action}</strong>
                {ev.created_at ? ` · ${new Date(ev.created_at).toLocaleString()}` : ''}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <div className="iep-builder__footer">
        {tabIndex > 0 ? (
          <button type="button" className="admin-btn admin-btn--ghost" disabled={saving} onClick={goBack}>
            Back
          </button>
        ) : null}
        {canEdit ? (
          <button type="button" className="admin-btn admin-btn--secondary" disabled={saving} onClick={save}>
            Save draft
          </button>
        ) : null}
        {tabIndex < IEP_TAB_ORDER.length - 1 ? (
          <button type="button" className="admin-btn admin-btn--secondary" disabled={saving} onClick={goNext}>
            Next
          </button>
        ) : null}
        <button type="button" className="admin-btn admin-btn--ghost" disabled={saving} onClick={openPreview}>
          Preview
        </button>
        <button type="button" className="admin-btn admin-btn--ghost" disabled={saving} onClick={downloadPdf}>
          Download PDF
        </button>
        {plan?.can_share_with_parent && canEdit ? (
          <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={startShareFlow}>
            Share with parent
          </button>
        ) : null}
        {plan?.status === 'INTERNAL_REVIEW' ? (
          <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={approvePlan}>
            Approve revision (CM)
          </button>
        ) : null}
        {plan?.status === 'PARENT_ACKNOWLEDGED' ? (
          <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={approvePlan}>
            Approve IEP
          </button>
        ) : null}
      </div>

      {previewOpen ? (
        <div className="iep-builder__preview-backdrop" role="dialog" aria-modal="true">
          <div className="iep-builder__preview">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>IEP preview</h3>
              <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setPreviewOpen(false)}>
                Close
              </button>
            </div>
            <div className="iep-builder__preview-body report-html-view" dangerouslySetInnerHTML={{ __html: previewHtml }} />
          </div>
        </div>
      ) : null}

      {shareFlowOpen ? (
        <div className="iep-builder__preview-backdrop" role="dialog" aria-modal="true">
          <div className="iep-builder__preview iep-builder__share-flow">
            <h3 style={{ margin: '0 0 12px' }}>Share IEP with parent</h3>
            <div className="iep-builder__share-steps">
              <span className={shareStep === 0 ? 'is-active' : ''}>1. Preview</span>
              <span className={shareStep === 1 ? 'is-active' : ''}>2. Attachments</span>
              <span className={shareStep === 2 ? 'is-active' : ''}>3. Confirm</span>
            </div>

            {shareStep === 0 ? (
              <>
                <div className="iep-builder__preview-body report-html-view" dangerouslySetInnerHTML={{ __html: previewHtml || '' }} />
                <label style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={previewAcknowledged}
                    onChange={(e) => setPreviewAcknowledged(e.target.checked)}
                  />
                  I have reviewed this preview and it is ready to share
                </label>
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary"
                    disabled={!previewAcknowledged}
                    onClick={() => setShareStep(1)}
                  >
                    Continue
                  </button>
                  <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setShareFlowOpen(false)}>
                    Cancel
                  </button>
                </div>
              </>
            ) : null}

            {shareStep === 1 ? (
              <>
                <p style={{ fontSize: '0.85rem', color: '#64748b' }}>Optional: attach supporting documents before sharing.</p>
                {canEdit ? (
                  <input
                    type="file"
                    multiple
                    onChange={async (e) => {
                      const files = [...(e.target.files || [])]
                      for (const f of files) {
                        try {
                          await uploadSupplement(f)
                        } catch (err) {
                          setError(err.message || 'Upload failed')
                        }
                      }
                      e.target.value = ''
                    }}
                  />
                ) : null}
                {suppIds.length > 0 ? (
                  <ul className="iep-builder__attach-list">
                    {suppIds.map((id) => (
                      <li key={id}>
                        {attachmentNames[id] || `Attachment #${id}`}
                        {canEdit ? (
                          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => removeSupplement(id)}>
                            Remove
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button type="button" className="admin-btn admin-btn--secondary" onClick={() => setShareStep(0)}>
                    Back
                  </button>
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary"
                    onClick={async () => {
                      if (canEdit) await save()
                      setShareStep(2)
                    }}
                  >
                    Continue
                  </button>
                </div>
              </>
            ) : null}

            {shareStep === 2 ? (
              <>
                <p>The parent will receive a notification and can acknowledge the IEP in their portal.</p>
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button type="button" className="admin-btn admin-btn--secondary" onClick={() => setShareStep(1)}>
                    Back
                  </button>
                  <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={shareWithParent}>
                    Confirm and share
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  )
}
