export function IepEvidenceDrawer({ open, onClose, availableGoals, observationApproved }) {
  if (!open) return null
  return (
    <aside className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-surface-container-lowest border-l border-outline-variant/30 z-40 p-6 overflow-y-auto clinical-shadow">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold m-0">Plan resources</h2>
        <button type="button" className="min-h-[44px] px-3" onClick={onClose}>
          Close
        </button>
      </div>
      {!observationApproved ? (
        <p className="text-sm text-amber-800">Observation not approved yet — manual context only.</p>
      ) : null}
      <section className="mb-6">
        <h3 className="text-xs font-bold uppercase font-mono text-outline">Available goals</h3>
        <ul className="mt-2 space-y-2 text-sm">
          {(availableGoals?.observation_candidates || []).slice(0, 8).map((g) => (
            <li key={g.id || g.label} className="p-2 rounded-lg bg-surface-container">
              {g.label}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h3 className="text-xs font-bold uppercase font-mono text-outline">Repository goals</h3>
        <ul className="mt-2 space-y-2 text-sm">
          {(availableGoals?.repository_goals || []).slice(0, 8).map((g) => (
            <li key={g.id} className="p-2 rounded-lg bg-surface-container">
              {g.label}
            </li>
          ))}
        </ul>
      </section>
    </aside>
  )
}
