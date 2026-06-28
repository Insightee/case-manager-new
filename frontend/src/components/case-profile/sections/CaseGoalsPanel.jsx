import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { GOAL_REPOSITORY_ENABLED } from '../../../lib/reportsRevampFlags.js'
import { domainLabel } from '../../../lib/clinicalDomains.js'
import { ClinicalMetricCard } from '../../clinical-ui/ClinicalMetricCard.jsx'
import { ClinicalGoalCard } from '../../clinical-ui/ClinicalGoalCard.jsx'
import { ClinicalStatusBadge } from '../../clinical-ui/ClinicalStatusBadge.jsx'
import { ClinicalEmptyState } from '../../clinical-ui/ClinicalEmptyState.jsx'
import { ClinicalCard } from '../../clinical-ui/ClinicalCard.jsx'

const STRENGTH_MAP = {
  strong_operational: 'strong_operational',
  moderate:           'moderate',
  weak:               'weak',
}

export function CaseGoalsPanel({ caseId, variant = 'therapist', canModerate = false }) {
  const [goals, setGoals] = useState([])
  const [iepGoals, setIepGoals] = useState([])
  const [evidenceGoals, setEvidenceGoals] = useState([])
  const [loading, setLoading] = useState(true)
  const [newGoal, setNewGoal] = useState({ label: '', domain_key: 'strengths_interests', rationale: '' })
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const tasks = [
        apiFetch(`/api/v1/cases/${caseId}/iep-plan`).catch(() => null),
        apiFetch(`/api/v1/cases/${caseId}/goals/evidence-summary`).catch(() => ({ goals: [] })),
      ]
      if (GOAL_REPOSITORY_ENABLED) {
        tasks.push(apiFetch(`/api/v1/cases/${caseId}/goal-candidates`).catch(() => ({ items: [] })))
      }
      const results = await Promise.all(tasks)
      const iep      = results[0]
      const evidence = results[1]
      const repo     = results[2]
      const sections = iep?.sections || {}
      const fromIep  = []
      if (sections.talent_development?.goals) {
        fromIep.push({ source: 'IEP', label: sections.talent_development.goals, domain_key: 'strengths_interests' })
      }
      if (sections.other_areas_of_need?.goals) {
        fromIep.push({ source: 'IEP', label: sections.other_areas_of_need.goals, domain_key: 'academics_learning' })
      }
      setIepGoals(fromIep)
      setGoals(repo?.items || [])
      setEvidenceGoals(evidence?.goals || [])
    } catch {
      setGoals([])
      setIepGoals([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => { load() }, [load])

  async function createCandidate(e) {
    e.preventDefault()
    if (!newGoal.label.trim()) return
    setMsg('')
    try {
      await apiFetch(`/api/v1/cases/${caseId}/goal-candidates`, {
        method: 'POST',
        body: JSON.stringify(newGoal),
      })
      setNewGoal({ label: '', domain_key: 'strengths_interests', rationale: '' })
      setMsg('Goal saved — pending case manager review.')
      await load()
    } catch (err) {
      setMsg(err.message || 'Could not save goal')
    }
  }

  if (loading) return <p className="ic-case-panel__loading">Loading goals…</p>

  /* Counts for metric cards */
  const totalGoals      = iepGoals.length + goals.length
  const withEvidence    = evidenceGoals.filter((e) => e.session_count > 0).length
  const needingEvidence = iepGoals.length - withEvidence
  const pendingReview   = goals.filter((g) => g.status === 'pending_review' || g.status === 'local').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
      <div className="clinical-page-header">
        <h2 className="clinical-section-heading">Goals</h2>
        <p className="clinical-section-subtitle">
          Active goals from the IEP plan and local candidates you propose for case manager approval.
        </p>
      </div>

      {/* Metric row */}
      <div className="clinical-metric-grid">
        <ClinicalMetricCard count={totalGoals}      label="Active Goals"          icon="🎯" />
        <ClinicalMetricCard count={withEvidence}    label="With Evidence"         icon="✅" />
        <ClinicalMetricCard count={Math.max(0, needingEvidence)} label="Needs Evidence" icon="⚠️" />
        <ClinicalMetricCard count={pendingReview}   label="Pending CM Review"     icon="🕐" />
      </div>

      {/* IEP goal cards */}
      {iepGoals.length > 0 ? (
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)', margin: '0 0 0.5rem' }}>
            Active IEP Goals
          </p>
          {iepGoals.map((g, i) => {
            const ev = evidenceGoals.find((e) => (e.label || '').includes((g.label || '').slice(0, 40)))
            return (
              <ClinicalGoalCard
                key={i}
                goal={{
                  number:          i + 1,
                  title:           g.label,
                  domainKey:       g.domain_key,
                  primaryObjective: domainLabel(g.domain_key),
                  status:          'ACTIVE',
                  evidenceStrength: STRENGTH_MAP[ev?.evidence_strength] || 'weak',
                  sessionsCount:    ev?.session_count,
                }}
              />
            )
          })}
        </div>
      ) : (
        <ClinicalEmptyState
          icon="🎯"
          title="No structured goal cards yet"
          body="Goals appear here once the IEP builder is populated by your case manager."
        />
      )}

      {/* Proposed goal candidates */}
      {goals.length > 0 ? (
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)', margin: '0 0 0.5rem' }}>
            {canModerate ? 'Goal Candidates' : 'Your Proposed Goals'}
          </p>
          {goals.map((g) => (
            <ClinicalGoalCard
              key={g.id}
              goal={{
                number:   '?',
                title:    g.label,
                domainKey: g.domain_key,
                status:   g.status === 'pending_review' ? 'PENDING_CM' : 'DRAFT',
              }}
            />
          ))}
        </div>
      ) : null}

      {/* Propose form (therapist only) */}
      {GOAL_REPOSITORY_ENABLED && variant === 'therapist' ? (
        <ClinicalCard>
          <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, margin: '0 0 0.375rem' }}>Propose a Goal</h4>
          <p className="cp-hint" style={{ margin: '0 0 0.75rem' }}>
            Goal suggestions go to your case manager for review before appearing in the IEP.
          </p>
          <form onSubmit={createCandidate} style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
            <label style={{ fontWeight: 600, fontSize: '0.875rem' }}>
              Goal statement
              <textarea
                value={newGoal.label}
                onChange={(e) => setNewGoal({ ...newGoal, label: e.target.value })}
                rows={3}
                style={{ display: 'block', width: '100%', marginTop: '0.3rem', padding: '0.625rem', borderRadius: '8px', border: '1px solid var(--clinical-border)', fontSize: '0.875rem', resize: 'vertical' }}
                placeholder="Child will…"
              />
            </label>
            {msg ? <p style={{ color: 'var(--clinical-green)', fontSize: '0.875rem' }}>{msg}</p> : null}
            <button type="submit" className="clinical-btn-primary" disabled={newGoal.label.trim().length < 5}>
              Save local candidate
            </button>
          </form>
        </ClinicalCard>
      ) : null}
    </div>
  )
}
