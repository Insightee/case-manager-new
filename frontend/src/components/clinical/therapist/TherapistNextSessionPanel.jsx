export function TherapistNextSessionPanel({ scheduleItems = [], summary, onOpenLogs }) {
  const next = scheduleItems.find((s) => s.status !== 'COMPLETED') || scheduleItems[0]
  const missingLogs = summary?.missing_items?.includes('session_logs')
  const staleGoals = (summary?.goal_coverage || []).filter((g) => g.stale)

  return (
    <section className="ic-case-panel cp-next-session" aria-labelledby="next-session-title">
      <h3 id="next-session-title">Next session focus</h3>
      {next ? (
        <p className="cp-next-session__when">
          {next.date || next.scheduled_date} · {next.startTime || next.start_time || 'Time TBD'}
        </p>
      ) : (
        <div className="clinical-empty-state" style={{ padding: '1rem 0' }}>
          <span className="clinical-empty-state__icon">📅</span>
          <p className="clinical-empty-state__title">No upcoming sessions</p>
          <p className="clinical-empty-state__body">Sessions appear here once scheduled by the case manager.</p>
        </div>
      )}
      <ul className="cp-next-session__focus">
        {missingLogs ? <li>Complete pending session logs before the next visit.</li> : null}
        {staleGoals.slice(0, 3).map((g) => (
          <li key={g.label}>Address goal: {g.label}</li>
        ))}
        {!missingLogs && !staleGoals.length ? <li>Review IEP goals and strategies for this session.</li> : null}
      </ul>
      {onOpenLogs ? (
        <button type="button" className="ic-btn ic-btn--ghost ic-btn--sm" onClick={onOpenLogs}>
          Open session logs
        </button>
      ) : null}
    </section>
  )
}
