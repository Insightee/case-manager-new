import { useState } from 'react'
import {
  INSIGHT_CERTAINTY_LABELS,
  deriveSessionInsights,
} from '../../../lib/structuredSessionEvidence.js'

const INSIGHT_TYPE_LABELS = {
  learned_today: 'What we learned today',
  recent_comparison: 'Compared with recent sessions',
  next_evidence: 'Useful next evidence opportunity',
  limitation: 'Evidence limitation',
}

function normalizeInsights(structuredSession) {
  const fromExtraction = (structuredSession.session_insights || []).map((item) => ({
    id: `${item.insight_type}-${item.title}`,
    type: item.insight_type,
    title: item.title || INSIGHT_TYPE_LABELS[item.insight_type] || 'Insight',
    summary: item.summary,
    certainty: item.certainty || 'single_session_signal',
    source: 'extraction',
  }))
  const derived = deriveSessionInsights(structuredSession).map((line, i) => ({
    id: `derived-${i}`,
    type: 'learned_today',
    title: 'From confirmed evidence',
    summary: line,
    certainty: 'single_session_signal',
    source: 'derived',
  }))
  return [...fromExtraction, ...derived].slice(0, 6)
}

export function ClinicalBrainInsightPanel({ structuredSession, onFeedback, compact = false }) {
  const insights = normalizeInsights(structuredSession)
  const [feedback, setFeedback] = useState({})

  if (!insights.length) {
    return (
      <div className="vsl-stitch__brain-panel vsl-stitch__brain-panel--empty">
        <p>Confirm goals and strategies first — insights will reflect what you verified today.</p>
      </div>
    )
  }

  function sendFeedback(insightId, value) {
    setFeedback((prev) => ({ ...prev, [insightId]: value }))
    onFeedback?.(insightId, value)
  }

  return (
    <div className="vsl-stitch__brain-panel" aria-label="Clinical Brain insights">
      <p className="vsl-stitch__brain-panel-lead">
        Cautious signals from confirmed evidence — not shared with families until you submit.
      </p>
      <ul className="vsl-stitch__brain-list">
        {insights.map((item) => (
          <li key={item.id} className="vsl-stitch__brain-item">
            <p className="vsl-stitch__brain-item-type">
              {INSIGHT_TYPE_LABELS[item.type] || item.title}
            </p>
            <p className="vsl-stitch__brain-item-summary">{item.summary}</p>
            <p className="vsl-stitch__brain-item-certainty">
              {INSIGHT_CERTAINTY_LABELS[item.certainty] || item.certainty}
            </p>
            {!compact ? (
              <div className="vsl-stitch__chip-row">
                {['accurate', 'needs_correction', 'not_useful'].map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={`vsl-stitch__chip vsl-stitch__chip--brain ${feedback[item.id] === value ? 'vsl-stitch__chip--on' : ''}`}
                    onClick={() => sendFeedback(item.id, value)}
                  >
                    {value === 'accurate' ? 'Accurate' : value === 'needs_correction' ? 'Needs correction' : 'Not useful'}
                  </button>
                ))}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
