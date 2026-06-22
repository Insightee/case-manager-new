import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { ClinicalTaxonomyPicker } from '../ClinicalTaxonomyPicker.jsx'

export function CreateStrategyModal({ caseId, logId, goalCardId, goalLabel = '', onClose, onCreated }) {
  const [form, setForm] = useState({
    label: '',
    expected_outcome: '',
    steps: ['', '', ''],
    core_domains: [],
    core_environments: [],
  })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (form.label.trim().length < 3) {
      setMsg('Add a strategy name.')
      return
    }
    setBusy(true)
    setMsg('')
    try {
      const steps = form.steps.filter((s) => s.trim())
      const created = await apiFetch(`/api/v1/cases/${caseId}/strategy-candidates`, {
        method: 'POST',
        body: JSON.stringify({
          label: form.label,
          strategy_steps: steps,
          how_to_use: steps.join('\n'),
          expected_outcome: form.expected_outcome,
          when_to_use: form.expected_outcome,
          environment_context: form.core_environments[0] || undefined,
          domain_key: form.core_domains[0] || undefined,
          core_domains: form.core_domains,
          core_environments: form.core_environments,
          linked_goal_card_id: goalCardId || undefined,
          source: 'therapist',
          source_daily_log_id: logId || undefined,
        }),
      })
      onCreated?.(created)
      onClose?.()
    } catch (err) {
      setMsg(err.message || 'Could not save strategy')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="gs-modal gs-engine" role="dialog" aria-modal="true" aria-labelledby="gs-create-strategy-title">
      <button type="button" className="gs-modal__backdrop" aria-label="Close" onClick={onClose} />
      <div className="gs-modal__sheet">
        <h2 id="gs-create-strategy-title">
          {goalLabel ? `New strategy for: ${goalLabel}` : 'Create New Strategy'}
        </h2>
        <p className="gs-hint">Three steps define how this strategy shows up in session logs.</p>
        <form onSubmit={handleSubmit} className="gs-form">
          <label className="gs-field">
            <span className="gs-field__label">Strategy name</span>
            <input
              type="text"
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="e.g., Sensory break routine"
            />
          </label>
          <ClinicalTaxonomyPicker
            domains={form.core_domains}
            environments={form.core_environments}
            onDomainsChange={(core_domains) => setForm({ ...form, core_domains })}
            onEnvironmentsChange={(core_environments) => setForm({ ...form, core_environments })}
          />
          {[0, 1, 2].map((i) => (
            <label key={i} className="gs-field">
              <span className="gs-field__label">Step {i + 1}</span>
              <input
                type="text"
                value={form.steps[i]}
                onChange={(e) => {
                  const next = [...form.steps]
                  next[i] = e.target.value
                  setForm({ ...form, steps: next })
                }}
              />
            </label>
          ))}
          <label className="gs-field">
            <span className="gs-field__label">Expected outcome</span>
            <textarea
              rows={2}
              value={form.expected_outcome}
              onChange={(e) => setForm({ ...form, expected_outcome: e.target.value })}
            />
          </label>
          {msg ? <p className="gs-error">{msg}</p> : null}
          <div className="gs-modal__actions">
            <button type="button" className="gs-btn gs-btn--ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="gs-btn gs-btn--primary" disabled={busy}>
              {busy ? 'Saving…' : 'Create strategy'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
