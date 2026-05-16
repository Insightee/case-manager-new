export function SectionHeader({
  title,
  subtitle,
  search,
  onSearchChange,
  primaryActionLabel,
  onPrimaryAction,
  secondaryActionLabel,
  onSecondaryAction,
}) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{title}</h2>
        <p className="mt-1 text-sm text-slate-500 sm:text-base">{subtitle}</p>
      </div>
      <div className="flex w-full flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end lg:w-auto">
        <input
          type="search"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search child, case ID…"
          className="min-h-[44px] w-full min-w-0 rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5 text-sm text-slate-900 shadow-sm outline-none ring-indigo-500/0 transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 sm:w-64"
          aria-label="Search reports"
        />
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {secondaryActionLabel && (
            <button
              type="button"
              onClick={onSecondaryAction}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
            >
              {secondaryActionLabel}
            </button>
          )}
          <button
            type="button"
            onClick={onPrimaryAction}
            className="inline-flex min-h-[44px] shrink-0 items-center justify-center rounded-xl bg-[#F97316] px-4 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-orange-600 hover:shadow-lg active:scale-[0.99]"
          >
            {primaryActionLabel}
          </button>
        </div>
      </div>
    </header>
  )
}
