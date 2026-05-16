function formatK(n) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(2)}L`
  if (n >= 1000) return `₹${(n / 1000).toFixed(1)}k`
  return `₹${n}`
}

export function EarningsTrendChart({ data }) {
  if (!data?.length) return null

  const max = Math.max(...data.map((d) => d.amountINR), 1)
  const last = data[data.length - 1]
  const prev = data[data.length - 2]
  const delta =
    prev && last ? (((last.amountINR - prev.amountINR) / prev.amountINR) * 100).toFixed(1) : null

  return (
    <section
      className="rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-[0_2px_12px_rgba(15,23,42,0.04)]"
      aria-label="Monthly earnings trend"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Monthly earnings trend</h3>
          <p className="mt-1 text-sm text-slate-500">Last {data.length} months · validated payouts</p>
        </div>
        {delta != null && (
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-bold ${
              Number(delta) >= 0 ? 'bg-emerald-50 text-emerald-800' : 'bg-rose-50 text-rose-800'
            }`}
          >
            {Number(delta) >= 0 ? '+' : ''}
            {delta}% MoM
          </span>
        )}
      </div>

      <div className="mt-6 flex h-40 items-end gap-1.5 sm:gap-2" role="img" aria-label="Bar chart of monthly amounts">
        {data.map((d) => {
          const h = Math.round((d.amountINR / max) * 100)
          return (
            <div key={d.month} className="flex min-w-0 flex-1 flex-col items-center gap-2">
              <div className="flex w-full flex-1 items-end justify-center">
                <div
                  className="w-full max-w-[48px] rounded-t-lg bg-gradient-to-t from-indigo-600 to-indigo-400 opacity-90 transition-all hover:opacity-100"
                  style={{ height: `${Math.max(h, 8)}%` }}
                  title={`${d.month}: ${formatK(d.amountINR)}`}
                />
              </div>
              <span className="max-w-full truncate text-center text-[10px] font-medium text-slate-500 sm:text-xs">
                {d.month.replace(/\d{4}/, '').trim()}
              </span>
            </div>
          )
        })}
      </div>
    </section>
  )
}
