/** Mobile-only Working Progress hero — Stitch reports_mobile_view */

export function WorkingProgressCard({ workingProgress, onAction }) {
  if (!workingProgress) return null
  const pct = Math.min(100, Math.max(0, Number(workingProgress.completion_pct) || 0))
  const evidence = workingProgress.evidence || {}
  const logsLine =
    evidence.session_logs_used != null
      ? `${evidence.session_logs_used}${evidence.session_logs_expected != null ? ` / ${evidence.session_logs_expected}` : ''} session logs synced`
      : null

  return (
    <section className="crt-working" aria-labelledby="crt-working-heading">
      <h2 id="crt-working-heading" className="crt-section-title">
        Working Progress
      </h2>
      <article className="crt-working-card">
        <div className="crt-working-card__glow" aria-hidden="true" />
        <div className="crt-working-card__inner">
          <div className="crt-working-card__head">
            <div>
              <p className="crt-working-card__eyebrow">Current focus</p>
              <h3 className="crt-working-card__title">{workingProgress.title}</h3>
            </div>
            <span className="crt-working-card__pill">{workingProgress.status_label || 'Draft'}</span>
          </div>
          <div className="crt-working-card__bar-wrap">
            <div className="crt-working-card__bar-labels">
              <span>Completion</span>
              <span>{pct}%</span>
            </div>
            <div
              className="crt-working-card__bar"
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div className="crt-working-card__bar-fill" style={{ width: `${pct}%` }} />
            </div>
            {logsLine ? <p className="crt-working-card__logs">{logsLine}</p> : null}
          </div>
          <div className="crt-working-card__actions">
            <button
              type="button"
              className="crt-working-card__continue"
              onClick={() => onAction?.(workingProgress)}
            >
              Continue Work
            </button>
          </div>
        </div>
      </article>
    </section>
  )
}
