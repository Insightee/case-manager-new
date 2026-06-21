export function StrategyCandidateReviewPanel({ caseId, pending = [], onUpdated }) {
  if (!pending.length) {
    return (
      <section className="cp-quality-card">
        <h3>Strategy candidates</h3>
        <p className="cp-quality-card__hint">No pending strategy candidates.</p>
      </section>
    )
  }
  return (
    <section className="cp-quality-card" aria-labelledby="strategy-review-title">
      <h3 id="strategy-review-title">Strategy candidates awaiting review</h3>
      <ul className="cp-quality-card__list">
        {pending.map((s) => (
          <li key={s.id}>
            {s.label}
            <span className="cp-quality-pill cp-quality-pill--draft">{s.status}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
