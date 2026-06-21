export function EvidenceCompletenessCard({ summary }) {
  if (!summary?.evidence_summary) return null
  const ev = summary.evidence_summary
  const strat = summary.strategy_coverage || {}
  const stats = [
    { label: 'Evidence events', value: ev.total_evidence_events ?? 0 },
    { label: 'Sessions missing goals', value: ev.sessions_without_goal_entries ?? 0 },
    { label: 'Strategies without outcome', value: ev.strategies_without_outcome ?? 0 },
    { label: 'Pending custom strategies', value: strat.pending_custom_count ?? 0 },
  ]
  return (
    <section className="clinical-quality-card" aria-labelledby="evidence-title">
      <h3 id="evidence-title" className="clinical-quality-card__title">Evidence completeness</h3>
      <div className="clinical-quality-card__stat-grid">
        {stats.map((s) => (
          <div key={s.label} className="clinical-quality-card__stat">
            <span className="clinical-quality-card__stat-value">{s.value}</span>
            <span className="clinical-quality-card__stat-label">{s.label}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
