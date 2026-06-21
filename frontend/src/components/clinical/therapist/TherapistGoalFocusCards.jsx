import { Link } from 'react-router-dom'

export function TherapistGoalFocusCards({ summary, basePath }) {
  const goals = (summary?.goal_coverage || []).slice(0, 4)
  if (!goals.length) {
    return (
      <section className="ic-case-panel">
        <h3>Active goals</h3>
        <div className="clinical-empty-state">
          <span className="clinical-empty-state__icon">🎯</span>
          <p className="clinical-empty-state__title">No active goals yet</p>
          <p className="clinical-empty-state__body">Goals appear once an active IEP is in place.</p>
          <Link to={`${basePath}?tab=reports&section=iep`} className="clinical-btn-ghost" style={{ marginTop: '0.5rem' }}>
            Open IEP
          </Link>
        </div>
      </section>
    )
  }
  return (
    <section className="ic-case-panel">
      <h3>Active goals</h3>
      <div className="cp-goal-focus-grid">
        {goals.map((g) => (
          <article key={g.label} className={`cp-goal-focus-card${g.stale ? ' is-stale' : ''}`}>
            <p className="cp-goal-focus-card__label">{g.label}</p>
            <p className="cp-goal-focus-card__meta">
              {g.sessions_addressed ?? 0} session(s) · {g.stale ? 'Needs evidence' : 'On track'}
            </p>
          </article>
        ))}
      </div>
      <Link to={`${basePath}?tab=goals`} className="ic-btn ic-btn--ghost ic-btn--sm">
        View all goals
      </Link>
    </section>
  )
}
