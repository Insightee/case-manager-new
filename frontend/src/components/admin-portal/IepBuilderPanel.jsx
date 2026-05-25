import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const EMPTY_ENV = { environment: '', strengths: '', supports_needed: '' }

export function IepBuilderPanel({ caseId }) {
  const [plan, setPlan] = useState(null)
  const [sections, setSections] = useState({
    about_child: '',
    referral: '',
    observations: '',
    learning_environments: [{ ...EMPTY_ENV }, { ...EMPTY_ENV }],
    interventions: '',
    signatures: '',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan`)
      setPlan(data)
      setSections({
        about_child: data.sections?.about_child || '',
        referral: data.sections?.referral || '',
        observations: data.sections?.observations || '',
        learning_environments:
          data.sections?.learning_environments?.length > 0
            ? data.sections.learning_environments
            : [{ ...EMPTY_ENV }, { ...EMPTY_ENV }],
        interventions: data.sections?.interventions || '',
        signatures: data.sections?.signatures || '',
      })
    } catch (err) {
      setError(err.message || 'Could not load IEP plan')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  function patchSection(key, value) {
    setSections((s) => ({ ...s, [key]: value }))
  }

  function patchEnv(index, field, value) {
    setSections((s) => {
      const rows = [...(s.learning_environments || [])]
      rows[index] = { ...rows[index], [field]: value }
      return { ...s, learning_environments: rows }
    })
  }

  function addEnvRow() {
    setSections((s) => ({
      ...s,
      learning_environments: [...(s.learning_environments || []), { ...EMPTY_ENV }],
    }))
  }

  async function save() {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const data = await apiFetch(`/api/v1/admin/cases/${caseId}/iep-plan`, {
        method: 'PUT',
        body: JSON.stringify({ sections }),
      })
      setPlan(data)
      setMessage('IEP draft saved.')
    } catch (err) {
      setError(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  async function shareWithParent() {
    setSaving(true)
    setError('')
    try {
      await save()
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

  if (loading) return <p className="text-sm text-slate-500">Loading IEP builder…</p>

  return (
    <section className="card" style={{ padding: 16 }}>
      <h3 style={{ marginTop: 0 }}>IEP document builder</h3>
      <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12 }}>
        Build the IEP from observation data and case profile. Share with parent when ready; they can acknowledge in the
        portal.
      </p>
      {plan ? (
        <p style={{ fontSize: '0.8rem', marginBottom: 12 }}>
          Version {plan.version} · {plan.status.replace(/_/g, ' ')}
        </p>
      ) : null}
      {error ? (
        <p role="alert" style={{ color: '#b91c1c' }}>
          {error}
        </p>
      ) : null}
      {message ? <p style={{ color: '#047857' }}>{message}</p> : null}

      {[
        { key: 'about_child', label: 'About the child' },
        { key: 'referral', label: 'Referral' },
        { key: 'observations', label: 'Observations (from checklist)' },
        { key: 'interventions', label: 'Interventions' },
        { key: 'signatures', label: 'Signatures' },
      ].map(({ key, label }) => (
        <div key={key} style={{ marginBottom: 14 }}>
          <label style={{ display: 'block', fontWeight: 600, marginBottom: 4 }}>{label}</label>
          <textarea
            value={sections[key] || ''}
            onChange={(e) => patchSection(key, e.target.value)}
            disabled={!plan?.can_edit}
            rows={key === 'observations' ? 6 : 3}
            style={{ width: '100%', padding: 8, borderRadius: 8, border: '1px solid #e2e8f0' }}
          />
        </div>
      ))}

      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <label style={{ fontWeight: 600 }}>Learning environments</label>
          {plan?.can_edit ? (
            <button type="button" className="admin-btn admin-btn--ghost" onClick={addEnvRow}>
              Add row
            </button>
          ) : null}
        </div>
        {(sections.learning_environments || []).map((row, idx) => (
          <div
            key={idx}
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: 8,
              marginTop: 8,
            }}
          >
            <input
              placeholder="Environment"
              value={row.environment}
              onChange={(e) => patchEnv(idx, 'environment', e.target.value)}
              disabled={!plan?.can_edit}
            />
            <input
              placeholder="Strengths"
              value={row.strengths}
              onChange={(e) => patchEnv(idx, 'strengths', e.target.value)}
              disabled={!plan?.can_edit}
            />
            <input
              placeholder="Supports needed"
              value={row.supports_needed}
              onChange={(e) => patchEnv(idx, 'supports_needed', e.target.value)}
              disabled={!plan?.can_edit}
            />
          </div>
        ))}
      </div>

      {plan?.can_edit ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" className="admin-btn admin-btn--secondary" disabled={saving} onClick={save}>
            Save draft
          </button>
          {plan?.can_share_with_parent ? (
            <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={shareWithParent}>
              Share with parent
            </button>
          ) : null}
        </div>
      ) : (
        <p style={{ fontSize: '0.85rem', color: '#64748b' }}>This version is already shared with the parent.</p>
      )}
    </section>
  )
}
