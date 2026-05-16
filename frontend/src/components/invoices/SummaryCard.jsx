function Trend({ value }) {
  if (value == null || Number.isNaN(value)) return null
  const positive = value >= 0
  return (
    <p className={`mt-2 text-xs font-semibold ${positive ? 'text-emerald-700' : 'text-rose-700'}`}>
      {positive ? '↑' : '↓'} {Math.abs(value).toFixed(1)}% vs last month
    </p>
  )
}

const CARDS = [
  {
    key: 'total',
    emoji: '💰',
    label: 'Total earnings (this month)',
    valueKey: 'totalEarningsThisMonthINR',
    trendKey: 'totalVsLastMonthPct',
    bg: 'bg-indigo-50/90',
    ring: 'ring-indigo-200/70',
    text: 'text-indigo-950',
  },
  {
    key: 'pending',
    emoji: '🟡',
    label: 'Pending amount',
    valueKey: 'pendingINR',
    trendKey: 'pendingVsLastMonthPct',
    bg: 'bg-amber-50/90',
    ring: 'ring-amber-200/80',
    text: 'text-amber-950',
  },
  {
    key: 'paid',
    emoji: '🟢',
    label: 'Paid amount',
    valueKey: 'paidINR',
    trendKey: 'paidVsLastMonthPct',
    bg: 'bg-emerald-50/90',
    ring: 'ring-emerald-200/80',
    text: 'text-emerald-950',
  },
  {
    key: 'queried',
    emoji: '🔴',
    label: 'Queried amount',
    valueKey: 'queriedINR',
    trendKey: 'queriedVsLastMonthPct',
    bg: 'bg-red-50/90',
    ring: 'ring-red-200/80',
    text: 'text-red-950',
  },
]

function formatInr(n) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n)
}

export function SummaryCard({ summary }) {
  const { trends } = summary

  return (
    <section aria-label="Payout overview" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {CARDS.map((c) => (
        <article
          key={c.key}
          className={`rounded-2xl border border-[#E2E8F0] p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)] transition-transform duration-200 hover:scale-[1.02] hover:shadow-[0_12px_28px_rgba(15,23,42,0.08)] ${c.bg} ring-1 ${c.ring}`}
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl" aria-hidden>
              {c.emoji}
            </span>
            <div className="min-w-0 flex-1">
              <p className={`text-xs font-semibold uppercase tracking-wide opacity-90 ${c.text}`}>{c.label}</p>
              <p className={`mt-2 text-2xl font-bold tabular-nums tracking-tight ${c.text}`}>
                {formatInr(summary[c.valueKey])}
              </p>
              {trends && <Trend value={trends[c.trendKey]} />}
            </div>
          </div>
        </article>
      ))}
    </section>
  )
}
