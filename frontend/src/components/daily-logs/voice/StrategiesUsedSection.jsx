import { useMemo, useState } from 'react'
import {
  addCustomSessionStrategy,
  buildPlanStrategyCards,
  ensurePlanStrategyRow,
  linkSessionStrategyToRepo,
  removeSessionStrategyRow,
  updateStrategyRow,
} from '../../../lib/structuredSessionEvidence.js'
import { searchGoalStrategyPool } from '../../../lib/sessionLogGoals.js'
import { sendStrategyCandidateForReview } from '../../../lib/voiceLogApi.js'

function strategyUseText(row) {
  return row?.implementation_summary || row?.spoken_phrase || row?.child_response_note || ''
}

function PlanStrategyCard({ card, onChange, structuredSession }) {
  const { plan, row } = card
  const useText = strategyUseText(row)
  const brief = plan.how_to_use || plan.when_to_use || ''

  function setUse(note) {
    onChange(
      ensurePlanStrategyRow(structuredSession, plan, {
        spoken_phrase: note,
        child_response_note: note,
        implementation_summary: note,
      }),
    )
  }

  return (
    <article className={`vsl-stitch__strategy-card ${useText ? 'vsl-stitch__strategy-card--helpful' : ''}`}>
      <div className="vsl-stitch__strategy-card-head">
        <div>
          <span className="vsl-stitch__field-label">Case plan strategy</span>
          <h4 className="vsl-stitch__strategy-title">{plan.label}</h4>
          {brief ? <p className="vsl-stitch__strategy-brief">{brief}</p> : null}
        </div>
      </div>
      <label className="vsl-stitch__field-label">How you used it this session</label>
      <textarea
        className="vsl-stitch__field vsl-stitch__field--inline vsl-stitch__field--sm"
        maxLength={500}
        placeholder="What you did with this strategy today — specific to this child and moment."
        value={useText}
        onChange={(e) => setUse(e.target.value)}
      />
    </article>
  )
}

function OtherStrategyCard({ row, onChange, structuredSession, repo, caseId, onSent }) {
  const [busy, setBusy] = useState(false)

  async function sendForReview() {
    setBusy(true)
    try {
      const created = await sendStrategyCandidateForReview(caseId, {
        label: row.strategy_label,
        howToUse: strategyUseText(row) || undefined,
      })
      onSent?.(row.strategy_label, created?.id)
    } finally {
      setBusy(false)
    }
  }

  const repoMatch = (repo?.strategies || []).find(
    (s) => (s.label || '').toLowerCase() === (row.strategy_label || '').toLowerCase(),
  )

  return (
    <article className="vsl-stitch__strategy-card">
      <div className="vsl-stitch__strategy-card-head">
        <div>
          <span className="vsl-stitch__field-label">Used today — not on case plan</span>
          <h4 className="vsl-stitch__strategy-title">{row.strategy_label}</h4>
        </div>
        <button
          type="button"
          className="vsl-stitch__text-link vsl-stitch__text-link--muted"
          onClick={() => onChange(removeSessionStrategyRow(structuredSession, row))}
        >
          Remove
        </button>
      </div>
      <textarea
        className="vsl-stitch__field vsl-stitch__field--inline vsl-stitch__field--sm"
        maxLength={500}
        placeholder="How this strategy was used in session…"
        value={strategyUseText(row)}
        onChange={(e) =>
          onChange(
            updateStrategyRow(structuredSession, row, {
              spoken_phrase: e.target.value,
              child_response_note: e.target.value,
              implementation_summary: e.target.value,
            }),
          )
        }
      />
      {repoMatch ? (
        <button
          type="button"
          className="vsl-stitch__text-link"
          onClick={() => onChange(linkSessionStrategyToRepo(structuredSession, row, repoMatch))}
        >
          Link to case plan: {repoMatch.label}
        </button>
      ) : (
        <button type="button" className="vsl-stitch__text-link" disabled={busy} onClick={sendForReview}>
          {busy ? 'Sending…' : 'Suggest adding to case plan'}
        </button>
      )}
    </article>
  )
}

function AddStrategyPanel({ structuredSession, onChange, repo }) {
  const [query, setQuery] = useState('')
  const [customOpen, setCustomOpen] = useState(false)
  const [customLabel, setCustomLabel] = useState('')
  const [customBrief, setCustomBrief] = useState('')
  const [customSteps, setCustomSteps] = useState(['', ''])

  const results = useMemo(() => {
    if (!query.trim()) return { goals: [], strategies: [] }
    return searchGoalStrategyPool(query, repo)
  }, [query, repo])

  const usedLabels = new Set(
    buildPlanStrategyCards(repo, structuredSession)
      .map((c) => (c.row?.strategy_label || c.plan?.label || '').toLowerCase())
      .filter(Boolean),
  )

  function addFromRepo(s) {
    onChange(
      ensurePlanStrategyRow(structuredSession, s, {
        spoken_phrase: '',
        implementation_summary: '',
      }),
    )
    setQuery('')
  }

  function saveCustom() {
    if (!customLabel.trim()) return
    onChange(
      addCustomSessionStrategy(structuredSession, {
        label: customLabel,
        brief: customBrief,
        steps: customSteps,
      }),
    )
    setCustomOpen(false)
    setCustomLabel('')
    setCustomBrief('')
    setCustomSteps(['', ''])
  }

  return (
    <div className="vsl-stitch__add-strategy">
      <input
        className="vsl-stitch__field vsl-stitch__field--search"
        placeholder="Search strategies from your library…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Search strategies"
      />
      {results.strategies.length ? (
        <div className="vsl-stitch__pill-row">
          {results.strategies
            .filter((s) => !usedLabels.has((s.label || '').toLowerCase()))
            .slice(0, 6)
            .map((s) => (
              <button
                key={s.strategy_id || s.label}
                type="button"
                className="vsl-stitch__pill vsl-stitch__pill--add"
                onClick={() => addFromRepo(s)}
              >
                + {s.label}
              </button>
            ))}
        </div>
      ) : null}
      {query.trim() && !results.strategies.length ? (
        <button type="button" className="vsl-stitch__text-link" onClick={() => { setCustomOpen(true); setCustomLabel(query.trim()) }}>
          No match — add &ldquo;{query.trim()}&rdquo; as new strategy
        </button>
      ) : null}
      {!customOpen ? (
        <button type="button" className="vsl-stitch__text-link vsl-stitch__text-link--muted" onClick={() => setCustomOpen(true)}>
          + Add strategy not in library
        </button>
      ) : (
        <div className="vsl-stitch__custom-strategy-form">
          <input
            className="vsl-stitch__field vsl-stitch__field--search"
            placeholder="Strategy name"
            value={customLabel}
            onChange={(e) => setCustomLabel(e.target.value)}
          />
          <textarea
            className="vsl-stitch__field vsl-stitch__field--inline vsl-stitch__field--sm"
            rows={2}
            placeholder="Strategy brief — when and why to use it"
            value={customBrief}
            onChange={(e) => setCustomBrief(e.target.value)}
          />
          {customSteps.map((step, i) => (
            <input
              key={i}
              className="vsl-stitch__field vsl-stitch__field--search"
              placeholder={`Step ${i + 1}`}
              value={step}
              onChange={(e) => {
                const next = [...customSteps]
                next[i] = e.target.value
                setCustomSteps(next)
              }}
            />
          ))}
          <div className="vsl-stitch__pill-row">
            <button type="button" className="vsl-stitch__pill vsl-stitch__pill--mint" onClick={saveCustom}>
              Save strategy
            </button>
            <button type="button" className="vsl-stitch__text-link" onClick={() => setCustomOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function StrategiesUsedSection({ structuredSession, onChange, repo, caseId }) {
  const cards = buildPlanStrategyCards(repo, structuredSession)
  const planCards = cards.filter((c) => c.kind === 'plan')
  const otherCards = cards.filter((c) => c.kind === 'other')
  const usedPlan = planCards.filter((c) => strategyUseText(c.row)).length

  return (
    <div className="vsl-stitch__strategies-stack">
      {planCards.length ? (
        <>
          <p className="vsl-stitch__section-hint">
            {usedPlan
              ? `${usedPlan} case plan strateg${usedPlan === 1 ? 'y' : 'ies'} used today — edit how each was applied.`
              : 'Your case plan strategies are listed below. Add how you used each one today.'}
          </p>
          {planCards.map((card, i) => (
            <PlanStrategyCard
              key={`plan-${card.plan.label}-${i}`}
              card={card}
              structuredSession={structuredSession}
              onChange={onChange}
            />
          ))}
        </>
      ) : (
        <p className="vsl-stitch__empty-hint">No strategies on the case plan yet — add what you used below.</p>
      )}

      {otherCards.map((card, i) => (
        <OtherStrategyCard
          key={`other-${card.row.strategy_label}-${i}`}
          row={card.row}
          structuredSession={structuredSession}
          onChange={onChange}
          repo={repo}
          caseId={caseId}
        />
      ))}

      <AddStrategyPanel structuredSession={structuredSession} onChange={onChange} repo={repo} />
    </div>
  )
}
