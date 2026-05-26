import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import {
  emptySections,
  LEARNING_STYLES,
  normalizeSections,
  PERFORMANCE_DOMAINS,
} from './iepBuilderDefaults.js'
import './admin-iep-builder.css'

const TABS = [
  { id: 'header', label: 'Header' },
  { id: 'clinical', label: 'Clinical' },
  { id: 'goals', label: 'Goals' },
  { id: 'verification', label: 'Verification' },
]

function Field({ label, children }) {
  return (
    <div className="iep-builder__field">
      <label>{label}</label>
      {children}
    </div>
  )
}

export function IepBuilderPanel({ caseId }) {
  const { canEditIep } = useModuleWrite()
  const [plan, setPlan] = useState(null)
  const [sections, setSections] = useState(emptySections)
  const [tab, setTab] = useState('header')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [previewHtml, setPreviewHtml] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan`)
      setPlan(data)
      setSections(normalizeSections(data.sections, data.case_context))
    } catch (err) {
      setError(err.message || 'Could not load IEP plan')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const productModule = plan?.case_context?.product_module || 'homecare'
  const canEdit = Boolean(plan?.can_edit && canEditIep(productModule))

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

  async function shareWithParent() {
    setSaving(true)
    setError('')
    try {
      if (canEdit) await save()
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan/share-with-parent`, {
        method: 'POST',
      })
      setPlan(data)
      setMessage('IEP shared with parent for acknowledgement.')
      await load()
    } catch (err) {
      setError(err.message || 'Share failed')
    } finally {
      setSaving(false)
    }
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

  return (
    <section className="card iep-builder">
      <div className="iep-builder__toolbar">
        <div>
          <h3 style={{ margin: 0 }}>IEP document builder</h3>
          {plan ? (
            <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '4px 0 0' }}>
              Version {plan.version} · {plan.status.replace(/_/g, ' ')}
            </p>
          ) : null}
        </div>
        <div className="iep-builder__tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              className={`iep-builder__tab${tab === t.id ? ' is-active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p role="alert" style={{ color: '#b91c1c' }}>
          {error}
        </p>
      ) : null}
      {message ? <p style={{ color: '#047857' }}>{message}</p> : null}

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
          <Field label="Therapist">
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
                  <input value={row.strengths} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'strengths', e.target.value)} />
                </Field>
                <Field label="Goals">
                  <input value={row.goals} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'goals', e.target.value)} />
                </Field>
                <Field label="Strategies">
                  <input value={row.strategies} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'strategies', e.target.value)} />
                </Field>
                <Field label="Supports needed">
                  <input value={row.supports_needed} disabled={!canEdit} onChange={(e) => patchEnv(idx, 'supports_needed', e.target.value)} />
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
            Therapist verified (replaces legacy signature line)
          </label>
          <Field label="Therapist name">
            <input value={v.therapist_name} disabled={!canEdit} onChange={(e) => patch('verification.therapist_name', e.target.value)} />
          </Field>
          <Field label="Therapist date">
            <input type="date" value={v.therapist_date || ''} disabled={!canEdit} onChange={(e) => patch('verification.therapist_date', e.target.value)} />
          </Field>
          <Field label="License no.">
            <input value={v.therapist_license_no} disabled={!canEdit} onChange={(e) => patch('verification.therapist_license_no', e.target.value)} />
          </Field>
          <Field label="Case manager">
            <input value={v.case_manager_name} disabled={!canEdit} onChange={(e) => patch('verification.case_manager_name', e.target.value)} />
          </Field>
          <Field label="Client name (parent ack)">
            <input value={v.client_name} disabled onChange={() => {}} />
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

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {canEdit ? (
          <button type="button" className="admin-btn admin-btn--secondary" disabled={saving} onClick={save}>
            Save draft
          </button>
        ) : null}
        <button type="button" className="admin-btn admin-btn--ghost" disabled={saving} onClick={openPreview}>
          Preview
        </button>
        {plan?.can_share_with_parent && canEdit ? (
          <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={shareWithParent}>
            Share with parent
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
            <div className="iep-builder__preview-body" dangerouslySetInnerHTML={{ __html: previewHtml }} />
          </div>
        </div>
      ) : null}
    </section>
  )
}
