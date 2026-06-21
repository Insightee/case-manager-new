export function GoalQualityReviewPanel({ caseId, pending = [], onUpdated }) {
  if (!pending.length) {
    return (
      <section className="cp-quality-card">
        <h3>Goal candidates</h3>
        <p className="cp-quality-card__hint">No pending goal candidates.</p>
      </section>
    )
  }
  return (
    <section className="cp-quality-card" aria-labelledby="goal-review-title">
      <h3 id="goal-review-title">Goal candidates awaiting review</h3>
      <ul className="cp-quality-card__list">
        {pending.map((g) => (
          <li key={g.id}>
            {g.label}
            <span className="cp-quality-pill cp-quality-pill--draft">{g.status}</span>
          </li>
        ))}
      </ul>
      <p className="cp-quality-card__hint">Approve from the goal repository admin tools or case goals tab.</p>
    </section>
  )
}
