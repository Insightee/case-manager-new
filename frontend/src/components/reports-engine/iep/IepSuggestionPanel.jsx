export function IepSuggestionPanel({ suggestions, onGenerate, generating, aiEnabled }) {
  if (!aiEnabled) return null
  const items = suggestions?.suggestions || []
  return (
    <section className="rounded-xl border border-lush-purple/30 bg-lush-purple/5 p-4">
      <div className="flex justify-between items-center gap-2 mb-3">
        <h3 className="text-sm font-bold m-0">IEP suggestions</h3>
        <button
          type="button"
          className="min-h-[44px] px-4 rounded-xl bg-lush-purple text-white text-sm font-bold"
          disabled={generating}
          onClick={onGenerate}
        >
          {generating ? 'Generating…' : 'Generate suggestions'}
        </button>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-on-surface-variant m-0">On-demand review hints — nothing generated yet.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((s, i) => (
            <li key={i} className="text-sm p-3 rounded-lg bg-white border border-outline-variant/30">
              {s.text}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
