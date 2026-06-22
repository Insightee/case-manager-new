import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { ClinicalTaxonomyPicker } from '../ClinicalTaxonomyPicker.jsx'

export function CreateGoalModal({ caseId, sessionId, logId, onClose, onCreated }) {
  const [form, setForm] = useState({
    label: '',
    rationale: '',
    baseline_state: '',
    desired_state: '',
    core_domains: [],
    core_environments: [],
  })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (form.label.trim().length < 5) {
      setMsg('Add a goal statement with at least a few words.')
      return
    }
    setBusy(true)
    setMsg('')
    try {
      const created = await apiFetch(`/api/v1/cases/${caseId}/goal-candidates`, {
        method: 'POST',
        body: JSON.stringify({
          label: form.label,
          goal_statement: form.label,
          rationale: form.rationale,
          baseline_state: form.baseline_state,
          desired_state: form.desired_state,
          domain_key: form.core_domains[0] || undefined,
          core_domains: form.core_domains,
          core_environments: form.core_environments,
          source: 'therapist',
          source_daily_log_id: logId || undefined,
          source_session_id: sessionId || undefined,
        }),
      })
      onCreated?.(created)
      onClose?.()
    } catch (err) {
      setMsg(err.message || 'Could not save goal')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="gs-modal gs-engine" role="dialog" aria-modal="true" aria-labelledby="gs-create-goal-title">
      <button type="button" className="gs-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="gs-modal__sheet">
        <h2 id="gs-create-goal-title">Create New Goal</h2>
        <p className="gs-hint">Saved to case repository — case manager reviews before org pool.</p>
        <form onSubmit={handleSubmit} className="gs-form">
          <label className="gs-field">
            <span className="gs-field__label">Goal statement</span>
            <textarea
              rows={3}
              maxLength={400}
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="What the child is working toward…"
            />
          </label>
          <label className="gs-field">
            <span className="gs-field__label">Baseline (optional)</span>
            <textarea
              rows={2}
              value={form.baseline_state}
              onChange={(e) => setForm({ ...form, baseline_state: e.target.value })}
            />
          </label>
          <label className="gs-field">
            <span className="gs-field__label">Desired state (optional)</span>
            <textarea
              rows={2}
              value={form.desired_state}
              onChange={(e) => setForm({ ...form, desired_state: e.target.value })}
            />
          </label>
          <ClinicalTaxonomyPicker
            domains={form.core_domains}
            environments={form.core_environments}
            onDomainsChange={(core_domains) => setForm({ ...form, core_domains })}
            onEnvironmentsChange={(core_environments) => setForm({ ...form, core_environments })}
          />
          {msg ? <p className="gs-error">{msg}</p> : null}
          <div className="gs-modal__actions">
            <button type="button" className="gs-btn gs-btn--ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="gs-btn gs-btn--primary" disabled={busy}>
              {busy ? 'Saving…' : 'Create goal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
