import { useState } from 'react'
import { IepBuilderPanel } from '../admin-portal/IepBuilderPanel.jsx'
import { planIntegrityScore } from '../../lib/iepPlanAdapter.js'
import { IEP_CARD_BUILDER, IEP_REVIEW_SUGGESTIONS } from '../../lib/reportsRevampFlags.js'
import { IepReviewSuggestionsPanel } from './IepReviewSuggestionsPanel.jsx'
import { ClinicalStrategyCard } from '../clinical-ui/ClinicalStrategyCard.jsx'
import { ClinicalProgressBar } from '../clinical-ui/ClinicalProgressBar.jsx'
import { ClinicalCard } from '../clinical-ui/ClinicalCard.jsx'

const RAIL_SECTIONS = [
  { id: 'overview',  label: 'Overview',          icon: '📋' },
  { id: 'observations', label: 'Observations',   icon: '👁' },
  { id: 'goals',     label: 'Goals & Metrics',   icon: '🎯' },
  { id: 'strategies', label: 'Strategies',       icon: '🔧' },
  { id: 'logs',      label: 'Session Logs',      icon: '📅' },
]

const DATA_POINTS = [
  'Goal addressed in session',
  'Strategy used',
  'Child starting state',
  'Duration of engagement',
  'Support level required',
  'Response to intervention',
  'Parent note included',
  'Progress signal',
]

const SUPPORT_LEVELS = ['Minimal', 'Moderate', 'High', 'Maximum']

const OUTCOME_OPTIONS = [
  'Emerging independence',
  'Generalised skill',
  'Consistent engagement',
  'Reduced prompting',
  'Needs adaptation',
  'Not addressed',
]

function SessionLogPreviewModal({ onClose }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.5)', zIndex: 50,
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
    }} role="dialog" aria-modal="true" aria-label="Session log preview">
      <div style={{
        background: '#fff', borderRadius: '16px 16px 0 0', padding: '1.5rem',
        width: '100%', maxWidth: '540px', maxHeight: '80vh', overflowY: 'auto',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>Preview Session Log</h3>
          <button type="button" onClick={onClose} aria-label="Close preview" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', color: 'var(--clinical-muted)' }}>✕</button>
        </div>
        <p className="cp-hint" style={{ marginBottom: '0.875rem' }}>
          This is a preview of how the session log form will look for strategies linked to this IEP. Actual submission uses the existing session log workflow.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          <div>
            <label style={{ fontWeight: 700, fontSize: '0.875rem', display: 'block', marginBottom: '0.375rem' }}>Session Date</label>
            <input type="date" disabled style={{ padding: '0.5rem 0.75rem', border: '1px solid var(--clinical-border)', borderRadius: '8px', width: '100%', fontSize: '0.875rem', background: '#f8f7fd' }} />
          </div>
          <div>
            <label style={{ fontWeight: 700, fontSize: '0.875rem', display: 'block', marginBottom: '0.375rem' }}>Goals Addressed</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
              {['Goal 1', 'Goal 2', 'Goal 3'].map((g) => (
                <span key={g} className="clinical-filter-chip is-active" style={{ pointerEvents: 'none' }}>{g}</span>
              ))}
            </div>
          </div>
          <div>
            <label style={{ fontWeight: 700, fontSize: '0.875rem', display: 'block', marginBottom: '0.375rem' }}>Support Level</label>
            <div className="clinical-support-levels">
              {SUPPORT_LEVELS.map((l, i) => (
                <span key={l} className={`clinical-support-level-btn${i === 1 ? ' is-active' : ''}`} style={{ cursor: 'default' }}>{l}</span>
              ))}
            </div>
          </div>
          <div>
            <label style={{ fontWeight: 700, fontSize: '0.875rem', display: 'block', marginBottom: '0.375rem' }}>Progress Signal</label>
            <div className="clinical-confidence-selector">
              {['No change', 'Emerging', 'Progressing', 'Consistent'].map((s, i) => (
                <span key={s} className={`clinical-confidence-btn${i === 2 ? ' is-active--consistent' : ''}`} style={{ cursor: 'default' }}>{s}</span>
              ))}
            </div>
          </div>
        </div>

        <button type="button" className="clinical-btn-secondary" onClick={onClose} style={{ width: '100%', marginTop: '1rem' }}>
          Close Preview
        </button>
      </div>
    </div>
  )
}

function StrategiesSection({ caseId }) {
  const [strategies] = useState([])
  const [selectedOutcomes, setSelectedOutcomes] = useState([])
  const [selectedLevel, setSelectedLevel] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  const toggleOutcome = (o) => setSelectedOutcomes((prev) =>
    prev.includes(o) ? prev.filter((x) => x !== o) : [...prev, o]
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
      {strategies.length > 0 ? (
        strategies.map((s, idx) => (
          <ClinicalStrategyCard key={s.id || idx} strategy={s} />
        ))
      ) : (
        <div className="clinical-empty-state cp-card">
          <span style={{ fontSize: '1.5rem' }} aria-hidden="true">🔧</span>
          <p className="clinical-empty-state__title">No strategies linked yet</p>
          <p className="clinical-empty-state__body">
            Add strategies from the Strategy Pool or create custom ones for this case.
          </p>
        </div>
      )}

      {/* Session Log Tracking panel */}
      <ClinicalCard>
        <h3 style={{ fontSize: '0.9375rem', fontWeight: 700, margin: '0 0 0.75rem' }}>
          Define Session Log Tracking
        </h3>

        <p style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 0.5rem', color: 'var(--clinical-muted)', textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.04em' }}>
          Required data points
        </p>
        <ul className="clinical-checklist" style={{ marginBottom: '0.875rem' }}>
          {DATA_POINTS.map((point) => (
            <li key={point} className="clinical-checklist__item">
              <span className="clinical-checklist__check" aria-hidden="true">✓</span>
              {point}
            </li>
          ))}
        </ul>

        <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)', margin: '0 0 0.375rem' }}>
          Outcome options
        </p>
        <div className="clinical-outcome-chips" style={{ marginBottom: '0.875rem' }}>
          {OUTCOME_OPTIONS.map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => toggleOutcome(o)}
              className={`clinical-outcome-chip${selectedOutcomes.includes(o) ? '' : ''}`}
              style={
                selectedOutcomes.includes(o)
                  ? {}
                  : { background: 'var(--clinical-surface)', color: 'var(--clinical-muted)', borderColor: 'var(--clinical-border)' }
              }
            >
              {o}
            </button>
          ))}
        </div>

        <p style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)', margin: '0 0 0.375rem' }}>
          Support level
        </p>
        <div className="clinical-support-levels" style={{ marginBottom: '0.875rem' }}>
          {SUPPORT_LEVELS.map((l) => (
            <button
              key={l}
              type="button"
              className={`clinical-support-level-btn${selectedLevel === l ? ' is-active' : ''}`}
              onClick={() => setSelectedLevel(selectedLevel === l ? null : l)}
            >
              {l}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="clinical-btn-secondary"
          onClick={() => setPreviewOpen(true)}
          style={{ marginTop: '0.25rem' }}
        >
          Preview Session Log →
        </button>
      </ClinicalCard>

      {previewOpen ? <SessionLogPreviewModal onClose={() => setPreviewOpen(false)} /> : null}
    </div>
  )
}

/** IEP Support Plan Builder — card layout shell over existing IepBuilderPanel backend contract. */
export function IepSupportPlanBuilder({ caseId, sections, activeSection, onSectionChange }) {
  const [railSection, setRailSection] = useState(activeSection || 'overview')
  const integrity = planIntegrityScore(sections || {})

  const handleRailChange = (id) => {
    setRailSection(id)
    onSectionChange?.(id)
  }

  return (
    <div className="cp-iep-builder" style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: '1rem', alignItems: 'start' }}>
      {/* Left rail */}
      <aside style={{
        background: 'var(--clinical-surface)', border: '1px solid var(--clinical-border)',
        borderRadius: 'var(--clinical-radius-card)', padding: '0.875rem',
        boxShadow: 'var(--clinical-shadow-card)', position: 'sticky', top: '4rem',
      }} aria-label="Plan sections">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
          <span style={{ fontSize: '0.6875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-muted)' }}>Plan Integrity</span>
          <strong style={{ color: 'var(--clinical-purple)', fontSize: '0.9375rem' }}>{integrity}%</strong>
        </div>
        <ClinicalProgressBar pct={integrity} showPct={false} />
        <nav style={{ marginTop: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.125rem' }}>
          {RAIL_SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => handleRailChange(s.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.375rem',
                padding: '0.5rem 0.5rem', borderRadius: '8px', border: 'none',
                background: railSection === s.id ? 'var(--clinical-purple-soft)' : 'none',
                color: railSection === s.id ? 'var(--clinical-purple)' : '#475569',
                fontWeight: railSection === s.id ? 700 : 500,
                fontSize: '0.8125rem', cursor: 'pointer', textAlign: 'left', minHeight: '36px',
              }}
            >
              <span aria-hidden="true">{s.icon}</span>
              {s.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Main area */}
      <div style={{ minWidth: 0 }}>
        {IEP_CARD_BUILDER && railSection !== 'strategies' ? (
          <div className="cp-hint cp-card" style={{ marginBottom: '0.75rem', background: 'var(--clinical-surface-soft)' }}>
            Card-based builder sections map to the existing IEP save and share-with-parent workflow.
          </div>
        ) : null}

        {railSection === 'strategies' ? (
          <StrategiesSection caseId={caseId} />
        ) : (
          <>
            {IEP_REVIEW_SUGGESTIONS ? <IepReviewSuggestionsPanel caseId={caseId} /> : null}
            <IepBuilderPanel caseId={caseId} />
          </>
        )}
      </div>
    </div>
  )
}
