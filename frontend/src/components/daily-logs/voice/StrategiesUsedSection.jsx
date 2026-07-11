import { useMemo, useState } from 'react'
import {
  STRATEGY_FEEDBACK,
  collectSessionStrategies,
  dismissRecommendation,
  markStrategyCandidateSent,
  recommendStrategies,
  saveRecommendationForNextSession,
  updateStrategyFeedback,
  updateStrategyRow,
} from '../../../lib/structuredSessionEvidence.js'
import { sendStrategyCandidateForReview } from '../../../lib/voiceLogApi.js'

const FEEDBACK_LABELS = {
  worked_well: 'Helpful',
  partially_worked: 'Partly helpful',
  did_not_work: 'Not helpful',
  not_observed: 'Not observed',
}

function StrategyCard({ row, sourceBadge, onFeedback, onNoteChange, extraActions }) {
  return (
    <article className="vsl-stitch__goal-card">
      <div className="vsl-stitch__badges">
        <span className="vsl-stitch__badge">{sourceBadge}</span>
        {row._goalLabel ? <span className="vsl-stitch__badge">Goal: {row._goalLabel}</span> : null}
      </div>
      <h4 style={{ margin: '0 0 6px' }}>{row.strategy_label}</h4>
      {row.spoken_phrase ? (
        <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '0 0 8px' }}>
          What was done: {row.spoken_phrase}
        </p>
      ) : null}
      {onNoteChange ? (
        <textarea
          className="vsl-stitch__textarea"
          rows={2}
          maxLength={400}
          placeholder="How did the child respond to this strategy? (optional)"
          value={row.child_response_note || ''}
          onChange={(e) => onNoteChange(e.target.value)}
        />
      ) : null}
      {onFeedback ? (
        <div className="vsl-stitch__chip-row" style={{ marginTop: 8 }}>
          {STRATEGY_FEEDBACK.map((id) => (
            <button
              key={id}
              type="button"
              className={`vsl-stitch__chip ${row.feedback === id ? 'vsl-stitch__chip--on' : ''}`}
              onClick={() => onFeedback(id)}
            >
              {FEEDBACK_LABELS[id]}
            </button>
          ))}
        </div>
      ) : null}
      {extraActions}
    </article>
  )
}

/**
 * Strategies used today — three groups:
 * active (case plan match), other identified (repo/no plan link → CM review),
 * recommended (max 2, deterministic from repo, no LLM).
 */
export function StrategiesUsedSection({ structuredSession, onChange, repo, caseId }) {
  const rows = collectSessionStrategies(structuredSession)
  const [busyLabel, setBusyLabel] = useState(null)
  const [notice, setNotice] = useState('')

  const planStrategyIds = useMemo(() => {
    const ids = new Set()
    const labels = new Set()
    for (const s of repo?.strategies || []) {
      if (s.strategy_id) ids.add(s.strategy_id)
      if (s.label) labels.add(s.label.toLowerCase())
    }
    return { ids, labels }
  }, [repo])

  const active = []
  const other = []
  for (const row of rows) {
    const inPlan =
      (row.strategy_id && planStrategyIds.ids.has(row.strategy_id)) ||
      planStrategyIds.labels.has((row.strategy_label || '').toLowerCase())
    if (inPlan) active.push(row)
    else other.push(row)
  }

  const recommended = recommendStrategies(structuredSession, repo)
  const sentLabels = new Set((structuredSession.strategy_candidates || []).map((c) => c.label))

  if (!rows.length && !recommended.length) return null

  function setNote(row, note) {
    onChange(updateStrategyRow(structuredSession, row, { child_response_note: note }))
  }

  async function sendStrategyToCm(row) {
    setBusyLabel(row.strategy_label)
    setNotice('')
    onChange(markStrategyCandidateSent(structuredSession, row.strategy_label, null))
    try {
      const created = await sendStrategyCandidateForReview(caseId, {
        label: row.strategy_label,
        howToUse: row.spoken_phrase || undefined,
      })
      setNotice(`Sent to your case manager: ${row.strategy_label}`)
      onChange((prev) => ({
        ...prev,
        strategy_candidates: (prev.strategy_candidates || []).map((c) =>
          c.label === row.strategy_label && !c.candidate_id ? { ...c, candidate_id: created?.id ?? null } : c,
        ),
      }))
    } catch (err) {
      setNotice(err.message || 'Could not reach the review queue — the strategy is still saved with this log.')
    } finally {
      setBusyLabel(null)
    }
  }

  return (
    <section aria-label="Strategies used today">
      <h3 className="vsl-stitch__section-head">Strategies used today</h3>

      {active.length ? (
        <>
          <p className="vsl-stitch__group-label">Active strategies used</p>
          {active.map((row, i) => (
            <StrategyCard
              key={`a-${i}`}
              row={row}
              sourceBadge="Case plan"
              onFeedback={(fb) => onChange(updateStrategyFeedback(structuredSession, row, fb))}
              onNoteChange={(note) => setNote(row, note)}
            />
          ))}
        </>
      ) : null}

      {other.length ? (
        <>
          <p className="vsl-stitch__group-label">Other strategies identified</p>
          {other.map((row, i) => {
            const sent = sentLabels.has(row.strategy_label)
            return (
              <StrategyCard
                key={`o-${i}`}
                row={row}
                sourceBadge="Not in case plan"
                onFeedback={(fb) => onChange(updateStrategyFeedback(structuredSession, row, fb))}
                onNoteChange={(note) => setNote(row, note)}
                extraActions={
                  <div className="vsl-stitch__chip-row" style={{ marginTop: 8 }}>
                    {sent ? (
                      <span className="vsl-stitch__badge vsl-stitch__badge--review">Sent for CM review</span>
                    ) : (
                      <button
                        type="button"
                        className="vsl-stitch__chip"
                        disabled={busyLabel === row.strategy_label}
                        onClick={() => sendStrategyToCm(row)}
                      >
                        {busyLabel === row.strategy_label ? 'Sending…' : 'Send for CM review'}
                      </button>
                    )}
                  </div>
                }
              />
            )
          })}
        </>
      ) : null}

      {recommended.length ? (
        <>
          <p className="vsl-stitch__group-label">Recommended for next session</p>
          {recommended.map((s) => (
            <article key={s.label} className="vsl-stitch__goal-card">
              <div className="vsl-stitch__badges">
                <span className="vsl-stitch__badge">From case plan · not used today</span>
              </div>
              <h4 style={{ margin: '0 0 6px' }}>{s.label}</h4>
              {s.when_to_use ? (
                <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '0 0 8px' }}>{s.when_to_use}</p>
              ) : null}
              <div className="vsl-stitch__chip-row">
                <button
                  type="button"
                  className="vsl-stitch__chip"
                  onClick={() => onChange(saveRecommendationForNextSession(structuredSession, s.label))}
                  disabled={(structuredSession.next_session_strategy_notes || []).includes(s.label)}
                >
                  {(structuredSession.next_session_strategy_notes || []).includes(s.label)
                    ? 'Saved for next session'
                    : 'Save for next session'}
                </button>
                <button
                  type="button"
                  className="vsl-stitch__chip"
                  onClick={() => onChange(dismissRecommendation(structuredSession, s.label))}
                >
                  Not relevant
                </button>
              </div>
            </article>
          ))}
        </>
      ) : null}

      {notice ? (
        <p role="status" style={{ fontSize: '0.8125rem', margin: '8px 0 0' }}>
          {notice}
        </p>
      ) : null}
    </section>
  )
}
