import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { GOAL_MODAL_DOMAIN_CHIPS } from '../../lib/clinicalUiContract.js'
import { SUPPORT_NEED_OPTIONS } from '../../lib/clinicalBrainFilters.js'
import { STRATEGY_SAVE_DESTINATION_LABELS } from '../../lib/clinicalBrainCopy.js'
import { CORE_ENVIRONMENTS } from '../../lib/coreClinicalTaxonomy.js'
import '../../styles/clinical-brain.css'

const ADMIN_STATUS_OPTIONS = [
  { id: 'draft', label: 'Draft' },
  { id: 'active', label: 'Active' },
  { id: 'deprecated', label: 'Deprecated' },
]

const SAVE_DESTINATIONS = [
  { id: 'session_log_only', label: STRATEGY_SAVE_DESTINATION_LABELS.session_log_only },
  { id: 'case_candidate', label: STRATEGY_SAVE_DESTINATION_LABELS.case_candidate },
  { id: 'cm_review', label: STRATEGY_SAVE_DESTINATION_LABELS.cm_review },
]

const EMPTY_THERAPIST = {
  label: '',
  domain: 'communication_aac',
  support_need: '',
  environment: 'classroom',
  description: '',
  when_to_use: '',
  avoid: '',
  steps: ['', '', ''],
  linked_goal_card_id: '',
  evidence_note: '',
  save_destination: 'case_candidate',
}

const EMPTY_ADMIN = {
  label: '',
  domains: ['communication_aac'],
  support_need: '',
  environments: ['classroom'],
  support_level: 'visual_support',
  description: '',
  rationale: '',
  steps: ['', '', ''],
  parent_explanation: '',
  avoid: '',
  materials: '',
  resource_link: '',
  status: 'draft',
}

export function SubmitCustomStrategyForm({
  caseId,
  mode = 'therapist',
  linkedGoalCardId,
  logId,
  onClose,
  onSaved,
  asDrawer = false,
}) {
  const isAdmin = mode === 'admin'
  const [form, setForm] = useState(isAdmin ? { ...EMPTY_ADMIN } : { ...EMPTY_THERAPIST, linked_goal_card_id: linkedGoalCardId || '' })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  function patch(p) {
    setForm((prev) => ({ ...prev, ...p }))
  }

  async function save(submitForReview = false) {
    if (!form.label.trim() || form.label.trim().length < 3) {
      setMsg('Add a strategy name (at least 3 characters).')
      return
    }
    setBusy(true)
    setMsg('')
    try {
      if (isAdmin) {
        // TODO(backend): dedicated org strategy pool create endpoint
        await apiFetch('/api/v1/admin/strategy-pool', {
          method: 'POST',
          body: JSON.stringify({
            label: form.label.trim(),
            domain_key: form.domains[0],
            core_environments: form.environments,
            when_to_use: form.description,
            how_to_use: form.steps.filter(Boolean).join('\n'),
            avoid: form.avoid,
            metadata: {
              support_need: form.support_need,
              support_level: form.support_level,
              environments: form.environments,
              parent_friendly_explanation: form.parent_explanation,
            },
            activate: submitForReview || form.status === 'active',
          }),
        })
      } else {
        const strategyType =
          form.save_destination === 'session_log_only'
            ? 'one_time'
            : form.save_destination === 'cm_review'
              ? 'case_specific'
              : 'case_specific'
        await apiFetch(`/api/v1/cases/${caseId}/strategy-candidates`, {
          method: 'POST',
          body: JSON.stringify({
            label: form.label.trim(),
            when_to_use: form.when_to_use || form.description,
            how_to_use: form.steps.filter(Boolean).join('\n'),
            avoid: form.avoid,
            domain_key: form.domain,
            environment_context: form.environment,
            linked_goal_card_id: form.linked_goal_card_id || linkedGoalCardId || undefined,
            source_daily_log_id: logId || undefined,
            source: submitForReview || form.save_destination === 'cm_review' ? 'cm_iep_review' : 'therapist',
            strategy_type: strategyType,
            strategy_steps: form.steps.filter(Boolean),
            expected_outcome: form.evidence_note || form.when_to_use,
          }),
        })
      }
      onSaved?.()
    } catch (err) {
      setMsg(err.message || 'Could not save strategy')
    } finally {
      setBusy(false)
    }
  }

  const shellClass = asDrawer ? 'cb-drawer is-open' : 'cb-strategy-picker'

  const body = (
    <>
      <header className={asDrawer ? 'mb-4' : 'cb-strategy-picker__head'}>
        <div className="flex items-center justify-between">
          <h2 className="m-0 text-lg font-bold">{isAdmin ? 'New strategy' : 'Propose strategy'}</h2>
          <button type="button" className="cb-filter-sheet__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {!isAdmin ? (
          <p className="gs-muted m-0 mt-1">Creates a case-specific strategy candidate.</p>
        ) : null}
      </header>

      <div className={asDrawer ? '' : 'cb-strategy-picker__body'}>
        <label className="sg-field">
          <span className="sg-field__label">Strategy name</span>
          <input value={form.label} onChange={(e) => patch({ label: e.target.value })} placeholder="Visual countdown" />
        </label>

        <span className="sg-field__label">Domain</span>
        <div className="sg-domain-grid mb-3">
          {GOAL_MODAL_DOMAIN_CHIPS.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`sg-domain-tile${(isAdmin ? form.domains[0] : form.domain) === c.id ? ' sg-domain-tile--active' : ''}`}
              onClick={() => patch(isAdmin ? { domains: [c.id] } : { domain: c.id })}
            >
              {c.label}
            </button>
          ))}
        </div>

        <span className="sg-field__label">Support need / issue</span>
        <div className="cb-filter-chips mb-3">
          {SUPPORT_NEED_OPTIONS.slice(0, 8).map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={`cb-filter-chip${form.support_need === opt.id ? ' is-active' : ''}`}
              onClick={() => patch({ support_need: opt.id })}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <span className="sg-field__label">Environment</span>
        <div className="cb-filter-chips mb-3">
          {CORE_ENVIRONMENTS.map((e) => {
            const active = isAdmin ? form.environments.includes(e.id) : form.environment === e.id
            return (
              <button
                key={e.id}
                type="button"
                className={`cb-filter-chip${active ? ' is-active' : ''}`}
                onClick={() => {
                  if (isAdmin) {
                    const next = active ? form.environments.filter((x) => x !== e.id) : [...form.environments, e.id]
                    patch({ environments: next })
                  } else {
                    patch({ environment: e.id })
                  }
                }}
              >
                {e.label}
              </button>
            )
          })}
        </div>

        <label className="sg-field">
          <span className="sg-field__label">{isAdmin ? 'Description' : 'How it was used'}</span>
          <textarea rows={3} value={form.description} onChange={(e) => patch({ description: e.target.value })} />
        </label>

        {!isAdmin ? (
          <>
            <label className="sg-field">
              <span className="sg-field__label">When it may help</span>
              <input value={form.when_to_use} onChange={(e) => patch({ when_to_use: e.target.value })} />
            </label>
            <label className="sg-field">
              <span className="sg-field__label">When not to use / caution</span>
              <input value={form.avoid} onChange={(e) => patch({ avoid: e.target.value })} />
            </label>
          </>
        ) : (
          <>
            <label className="sg-field">
              <span className="sg-field__label">Clinical rationale</span>
              <textarea rows={2} value={form.rationale} onChange={(e) => patch({ rationale: e.target.value })} />
            </label>
            <label className="sg-field">
              <span className="sg-field__label">Parent-friendly explanation</span>
              <textarea rows={2} value={form.parent_explanation} onChange={(e) => patch({ parent_explanation: e.target.value })} />
            </label>
            <label className="sg-field">
              <span className="sg-field__label">Cautions</span>
              <input value={form.avoid} onChange={(e) => patch({ avoid: e.target.value })} />
            </label>
            <label className="sg-field">
              <span className="sg-field__label">Resource link</span>
              <input value={form.resource_link} onChange={(e) => patch({ resource_link: e.target.value })} />
            </label>
          </>
        )}

        <span className="sg-field__label">Implementation steps</span>
        {[0, 1, 2].map((i) => (
          <label key={i} className="sg-field">
            <span className="sg-field__label">Step {i + 1}</span>
            <input
              value={form.steps[i]}
              onChange={(e) => {
                const next = [...form.steps]
                next[i] = e.target.value
                patch({ steps: next })
              }}
            />
          </label>
        ))}

        {!isAdmin ? (
          <>
            <span className="sg-field__label">Save destination</span>
            <div className="cb-goal-use-cards mb-3">
              {SAVE_DESTINATIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`cb-goal-use-card${form.save_destination === opt.id ? ' is-selected' : ''}`}
                  onClick={() => patch({ save_destination: opt.id })}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </>
        ) : (
          <span className="sg-field__label">Status</span>
        )}
        {isAdmin ? (
          <div className="cb-filter-chips mb-3">
            {ADMIN_STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`cb-filter-chip${form.status === opt.id ? ' is-active' : ''}`}
                onClick={() => patch({ status: opt.id })}
              >
                {opt.label}
              </button>
            ))}
          </div>
        ) : null}

        {msg ? <p className="sg-error">{msg}</p> : null}
      </div>

      <footer className={asDrawer ? 'mt-4 flex gap-2' : 'cb-strategy-picker__foot'}>
        <button type="button" className="cb-btn" disabled={busy} onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="cb-btn" disabled={busy} onClick={() => save(false)}>
          Save draft
        </button>
        <button type="button" className="cb-btn cb-btn--primary" disabled={busy} onClick={() => save(true)}>
          {isAdmin ? 'Submit for review' : 'Submit for CM review'}
        </button>
      </footer>
    </>
  )

  if (asDrawer) {
    return (
      <div className={shellClass} role="dialog" aria-modal="true">
        <button type="button" className="cb-drawer__backdrop" aria-label="Close" onClick={onClose} />
        <div className="cb-drawer__panel">{body}</div>
      </div>
    )
  }

  return <div className={shellClass}>{body}</div>
}
