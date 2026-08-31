/**
 * Homecare prepaid/per-session (non-counselling): next-month session count only.
 * Informational — not billed in the current payout.
 */
export function NextMonthSessionPlanEditor({ plan, onChange }) {
  const count = Number(plan?.session_count || 0)
  const notes = plan?.notes || ''

  function emit(next) {
    onChange?.(next)
  }

  return (
    <div className="rounded-xl border border-sky-100 bg-sky-50/70 p-3">
      <p className="text-sm font-semibold text-sky-950">Next month sessions</p>
      <p className="mt-1 text-xs text-sky-900/80">
        How many sessions do you expect next month? Saved on your invoice for reference — not billed this month.
      </p>

      <label className="mt-3 block text-xs font-medium text-slate-700">
        Number of sessions
        <input
          type="number"
          min={0}
          max={60}
          step={1}
          value={Number.isFinite(count) ? count : 0}
          onChange={(e) => {
            const n = Math.max(0, Math.min(60, parseInt(e.target.value || '0', 10) || 0))
            emit({ notes, session_count: n })
          }}
          className="mt-1 min-h-[44px] w-full rounded-lg border border-[#E2E8F0] px-3 text-sm"
        />
      </label>

      <label className="mt-3 block text-xs font-medium text-slate-700">
        Notes (optional)
        <textarea
          className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
          rows={2}
          value={notes}
          onChange={(e) => emit({ notes: e.target.value, session_count: count })}
          placeholder="Anything finance or your CM should know"
        />
      </label>
    </div>
  )
}
