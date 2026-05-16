const CARDS = [
  {
    key: 'draft',
    label: 'Draft',
    emoji: '🟡',
    bg: 'bg-amber-50/90',
    ring: 'ring-amber-200/80',
    text: 'text-amber-950',
  },
  {
    key: 'underReview',
    label: 'Under Review',
    emoji: '🔵',
    bg: 'bg-sky-50/90',
    ring: 'ring-sky-200/80',
    text: 'text-sky-950',
  },
  {
    key: 'published',
    label: 'Published',
    emoji: '🟢',
    bg: 'bg-emerald-50/90',
    ring: 'ring-emerald-200/80',
    text: 'text-emerald-950',
  },
  {
    key: 'overdue',
    label: 'Overdue',
    emoji: '🔴',
    bg: 'bg-red-50/90',
    ring: 'ring-red-200/80',
    text: 'text-red-950',
  },
]

export function PipelineStats({ counts, activeFilter, onFilter }) {
  return (
    <section aria-label="Report pipeline overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {CARDS.map((c) => {
        const value = counts[c.key] ?? 0
        const isActive = activeFilter === c.key
        return (
          <button
            key={c.key}
            type="button"
            onClick={() => onFilter(c.key)}
            className={`flex items-center gap-3 rounded-2xl border border-[#E2E8F0] p-4 text-left shadow-[0_2px_12px_rgba(15,23,42,0.04)] transition-all hover:scale-[1.02] hover:shadow-[0_12px_28px_rgba(15,23,42,0.08)] ${
              c.bg
            } ${isActive ? `ring-2 ${c.ring} ring-offset-2 ring-offset-[#F8FAFC]` : ''}`}
          >
            <span className="text-2xl" aria-hidden>
              {c.emoji}
            </span>
            <div className="min-w-0 flex-1">
              <p className={`text-xs font-semibold uppercase tracking-wide ${c.text} opacity-90`}>{c.label}</p>
              <p className={`mt-1 text-2xl font-bold tabular-nums ${c.text}`}>{value}</p>
            </div>
          </button>
        )
      })}
    </section>
  )
}
