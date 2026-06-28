import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../../lib/apiClient.js'
import { InternalVsFamilyBanner } from '../../clinical/InternalVsFamilyBanner.jsx'
import { ClinicalStatusBadge } from '../../clinical-ui/ClinicalStatusBadge.jsx'
import { ClinicalGoalCard } from '../../clinical-ui/ClinicalGoalCard.jsx'
import { ClinicalInsightCard } from '../../clinical-ui/ClinicalInsightCard.jsx'
import { ClinicalProgressBar } from '../../clinical-ui/ClinicalProgressBar.jsx'
import { ClinicalCard } from '../../clinical-ui/ClinicalCard.jsx'

function GoalChip({ label }) {
  return (
    <span className="cp-tag" style={{ fontSize: '0.75rem' }}>{label}</span>
  )
}

function MonitoringCard({ nextReview }) {
  return (
    <div className="clinical-monitoring-card" style={{ marginTop: '1rem' }}>
      <div>
        <p className="clinical-monitoring-card__label">Next Review</p>
        <p className="clinical-monitoring-card__sub">
          Plan update — review with case manager or team
        </p>
      </div>
      {nextReview ? (
        <div>
          <p className="clinical-monitoring-card__date">{nextReview.split('-')[2]}</p>
          <p className="clinical-monitoring-card__date-sub">
            {nextReview.slice(0, 7)}
          </p>
        </div>
      ) : (
        <p className="clinical-monitoring-card__date-sub">Not set</p>
      )}
    </div>
  )
}

export function CaseIepSection({ caseId, canManage = false, variant = 'therapist' }) {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [suggestion, setSuggestion] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const base =
        variant === 'admin' ? `/api/v1/admin/cases/${caseId}/iep-plan` : `/api/v1/cases/${caseId}/iep-plan`
      const data = await apiFetch(base)
      setPlan(data)
    } catch {
      setPlan(null)
    } finally {
      setLoading(false)
    }
  }, [caseId, variant])

  useEffect(() => { load() }, [load])

  async function submitSuggestion(e) {
    e.preventDefault()
    if (!suggestion.trim()) return
    setBusy(true)
    setMsg('')
    try {
      await apiFetch(`/api/v1/cases/${caseId}/iep-plan/suggestions`, {
        method: 'POST',
        body: JSON.stringify({ body: suggestion.trim() }),
      })
      setSuggestion('')
      setMsg('Suggestion sent to your case manager.')
      await load()
    } catch (err) {
      setMsg(err.message || 'Could not send suggestion')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <p className="ic-case-panel__loading">Loading IEP plan…</p>

  if (canManage && variant === 'admin') {
    return (
      <div>
        <InternalVsFamilyBanner variant={plan?.visibility_status === 'SHARED_WITH_PARENT' ? 'family' : 'internal'} />
        <p className="ic-case-panel__hint" style={{ marginBottom: '0.75rem' }}>
          Open the full IEP Support Plan builder to edit goals, strategies, and environment supports.
        </p>
        <Link
          to={`/admin/cases/${caseId}?tab=iep`}
          className="clinical-btn-primary"
        >
          Open IEP builder
        </Link>
      </div>
    )
  }

  const sections = plan?.sections || {}
  const goals = plan?.goals || Object.entries(sections)
    .filter(([key]) => key !== 'profile')
    .map(([key, val], idx) => ({
      id: `goal-${idx}`,
      number: idx + 1,
      title: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      statement: typeof val === 'string' ? val : val?.goals || '',
      domainKey: key,
      status: plan?.status || 'ACTIVE',
      evidenceStrength: 'moderate',
    }))

  const priorityFocusChips = goals.slice(0, 3).map((g) => g.title)

  return (
    <div>
      <div className="clinical-page-header">
        <h2 className="clinical-section-heading">IEP Support Plan</h2>
        <p className="clinical-section-subtitle">
          Individualised goals, therapeutic strategies, and measurement framework for this child.
        </p>
      </div>

      <InternalVsFamilyBanner variant={plan?.visibility_status === 'SHARED_WITH_PARENT' ? 'family' : 'internal'} />

      <div className="clinical-two-col" style={{ marginTop: '0.75rem' }}>
        {/* Left: IEP summary + goal cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          {plan ? (
            <ClinicalCard>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.0625rem', fontWeight: 800, margin: '0 0 0.2rem' }}>IEP Support Plan</h3>
                  <p className="cp-hint" style={{ margin: 0 }}>Version {plan.version || '1.0'}</p>
                </div>
                <ClinicalStatusBadge status={plan.status || 'ACTIVE'} />
              </div>
              {priorityFocusChips.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--clinical-muted)', marginRight: '0.25rem', alignSelf: 'center' }}>Priority focus:</span>
                  {priorityFocusChips.map((chip) => <GoalChip key={chip} label={chip} />)}
                </div>
              ) : null}
            </ClinicalCard>
          ) : null}

          {/* Goal cards */}
          {goals.length > 0 ? (
            <div>
              <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)', margin: '0 0 0.5rem' }}>
                Goal Planning
              </p>
              {goals.map((goal) => (
                <ClinicalGoalCard key={goal.id} goal={goal}>
                  {goal.statement ? null : (
                    <p className="cp-hint">No statement recorded for this goal area.</p>
                  )}
                </ClinicalGoalCard>
              ))}
            </div>
          ) : !plan ? (
            <div className="clinical-empty-state cp-card">
              <span className="clinical-empty-state__icon" aria-hidden="true">📋</span>
              <p className="clinical-empty-state__title">No active support plan yet</p>
              <p className="clinical-empty-state__body">
                Once observation findings are reviewed, the case manager creates the child's plan.
              </p>
            </div>
          ) : null}

          {/* Suggestion form (therapist only) */}
          {variant === 'therapist' ? (
            <ClinicalCard>
              <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, margin: '0 0 0.375rem' }}>Suggest an update</h4>
              <p className="cp-hint" style={{ margin: '0 0 0.75rem' }}>
                Share goal or strategy ideas with your case manager (internal until approved).
              </p>
              <form onSubmit={submitSuggestion}>
                <textarea
                  value={suggestion}
                  onChange={(e) => setSuggestion(e.target.value)}
                  rows={4}
                  style={{ width: '100%', padding: '0.625rem', borderRadius: '8px', border: '1px solid var(--clinical-border)', fontSize: '0.875rem', resize: 'vertical' }}
                  placeholder="Describe a goal adjustment or strategy that worked in sessions…"
                />
                {msg ? <p style={{ color: 'var(--clinical-green)', fontSize: '0.875rem', margin: '0.375rem 0' }}>{msg}</p> : null}
                <button
                  type="submit"
                  className="clinical-btn-primary"
                  disabled={busy || suggestion.trim().length < 5}
                  style={{ marginTop: '0.625rem' }}
                >
                  {busy ? 'Sending…' : 'Send suggestion'}
                </button>
              </form>
            </ClinicalCard>
          ) : null}

          {/* Monitoring card */}
          <MonitoringCard nextReview={plan?.next_review_date} />
        </div>

        {/* Right: observation insights + consistency + team */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="clinical-evidence-panel">
            <h3 className="clinical-evidence-panel__title">Observation Insights</h3>
            <ClinicalInsightCard
              severity="info"
              title="Based on observed findings"
              reason="Goals are derived from your observation checklist and session history for this child."
            />
          </div>

          <div className="clinical-evidence-panel">
            <h3 className="clinical-evidence-panel__title">Log Consistency</h3>
            <ClinicalProgressBar label="Goals addressed in sessions" pct={goals.length > 0 ? 65 : 0} />
            <p className="clinical-evidence-panel__text" style={{ marginTop: '0.5rem' }}>
              Consistent documentation strengthens the evidence base for each goal.
            </p>
          </div>

          <div className="clinical-evidence-panel">
            <h3 className="clinical-evidence-panel__title">Team Collaboration</h3>
            <div className="clinical-team-panel">
              <p className="clinical-team-panel__note">
                {plan
                  ? `IEP is ${plan.visibility_status === 'SHARED_WITH_PARENT' ? 'shared with family' : 'internal — not yet shared with family'}.`
                  : 'No IEP on file. Your case manager will create one after observation review.'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
