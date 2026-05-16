import { useCallback, useMemo, useState } from 'react'
import dailyLogsData from '../../data/dailyLogs.json'
import { ChecklistPanel } from './ChecklistPanel.jsx'
import { FilterBar } from './FilterBar.jsx'
import { LogCard } from './LogCard.jsx'
import { QuickLogCard } from './QuickLogCard.jsx'

function Toast({ message, visible, onDismiss }) {
  if (!visible) return null
  return (
    <div
      role="status"
      className="fixed right-4 top-4 z-[100] flex max-w-sm items-start gap-3 rounded-xl border border-emerald-200 bg-white px-4 py-3 shadow-[0_12px_40px_rgba(15,23,42,0.12)]"
    >
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
        ✓
      </span>
      <div>
        <p className="font-semibold text-slate-900">Log saved</p>
        <p className="text-sm text-slate-600">{message}</p>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="ml-2 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  )
}

function PageHeader({ search, onSearchChange, onNewLog }) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">Daily Logs</h2>
        <p className="mt-1 text-sm text-slate-500 sm:text-base">
          Submit and track your service logs for each session
        </p>
      </div>
      <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-end lg:w-auto">
        <input
          type="search"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search child, case ID…"
          className="min-h-[44px] w-full min-w-0 rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5 text-sm text-slate-900 shadow-sm outline-none ring-indigo-500/0 transition focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 sm:w-64"
          aria-label="Search logs"
        />
        <button
          type="button"
          onClick={onNewLog}
          className="inline-flex min-h-[44px] shrink-0 items-center justify-center rounded-xl bg-[#F97316] px-4 py-2.5 text-sm font-semibold text-white shadow-md transition hover:bg-orange-600 hover:shadow-lg active:scale-[0.99]"
        >
          + New Daily Log
        </button>
      </div>
    </header>
  )
}

function AttentionCard({ item, onCompleteLog }) {
  const isMissing = item.kind === 'missing'
  return (
    <article
      className={`rounded-2xl border p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)] transition-transform duration-200 hover:scale-[1.01] hover:shadow-[0_12px_32px_rgba(15,23,42,0.08)] ${
        isMissing
          ? 'border-red-200 bg-gradient-to-br from-red-50/90 to-white'
          : 'border-amber-200 bg-gradient-to-br from-amber-50/90 to-white'
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span
            className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${
              isMissing ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-900'
            }`}
          >
            {isMissing ? 'Missing' : 'Pending'}
          </span>
          <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-indigo-600">{item.caseId}</p>
          <p className="text-lg font-semibold text-slate-900">{item.child}</p>
          <p className="mt-1 text-sm font-medium text-slate-600">{item.dueLabel}</p>
        </div>
        <button
          type="button"
          onClick={() => onCompleteLog(item.caseId)}
          className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
        >
          Complete log
        </button>
      </div>
    </article>
  )
}

export function DailyLogsPage() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedCaseId, setSelectedCaseId] = useState(dailyLogsData.cases[0]?.caseId ?? '')
  const [logs, setLogs] = useState(dailyLogsData.recentLogs)
  const [checklist, setChecklist] = useState(
    dailyLogsData.checklist.map((c) => ({ ...c })),
  )
  const [toast, setToast] = useState({ visible: false, message: '' })
  const [formSeed, setFormSeed] = useState(null)

  const clearFormSeed = useCallback(() => {
    setFormSeed(null)
  }, [])

  const showToast = useCallback((message) => {
    setToast({ visible: true, message })
    window.setTimeout(() => setToast((t) => ({ ...t, visible: false })), 4200)
  }, [])

  const scrollToQuickLog = () => {
    document.getElementById('quick-log-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleNewLog = () => {
    scrollToQuickLog()
  }

  const handleCompleteAttention = (caseId) => {
    setSelectedCaseId(caseId)
    scrollToQuickLog()
  }

  const handleQuickSubmit = useCallback(
    ({ caseId, durationMinutes, activities, observations }) => {
      const child = dailyLogsData.cases.find((c) => c.caseId === caseId)?.child ?? '—'
      const today = new Date().toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
      const newLog = {
        id: `log-${Date.now()}`,
        caseId,
        child,
        date: today.replace(/ /g, ' '),
        durationMinutes,
        status: 'submitted',
        activities,
        observations,
      }
      setLogs((prev) => [newLog, ...prev])
      showToast(`Session for ${child} (${caseId}) submitted.`)
    },
    [showToast],
  )

  const filteredLogs = useMemo(() => {
    const q = search.trim().toLowerCase()
    return logs.filter((log) => {
      const match =
        !q ||
        log.caseId.toLowerCase().includes(q) ||
        (log.child && log.child.toLowerCase().includes(q))
      const st = statusFilter === 'all' || log.status === statusFilter
      return match && st
    })
  }, [logs, search, statusFilter])

  const handleDuplicate = useCallback((log) => {
    setSelectedCaseId(log.caseId)
    const last = dailyLogsData.lastSessionByCase[log.caseId]
    setFormSeed({
      id: `seed-${Date.now()}`,
      durationMinutes: log.durationMinutes ?? last?.durationMinutes ?? 45,
      activities:
        log.activities?.length ? log.activities : last?.activities ?? [],
      observations: log.observations ?? last?.observations ?? '',
    })
    scrollToQuickLog()
  }, [])

  const handleCheckToggle = (id) => {
    setChecklist((prev) => prev.map((i) => (i.id === id ? { ...i, done: !i.done } : i)))
  }

  const noLogsAtAll = logs.length === 0
  const emptyFiltered = filteredLogs.length === 0

  return (
    <div className="relative flex min-h-full flex-col gap-6 rounded-2xl bg-[#F8FAFC] px-1 py-2 pb-24 sm:px-3 sm:py-4 lg:pb-8">
      <Toast
        message={toast.message}
        visible={toast.visible}
        onDismiss={() => setToast((t) => ({ ...t, visible: false }))}
      />

      <PageHeader search={search} onSearchChange={setSearch} onNewLog={handleNewLog} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-6">
          <QuickLogCard
            cases={dailyLogsData.cases}
            activityTags={dailyLogsData.activityTags}
            lastSessionByCase={dailyLogsData.lastSessionByCase}
            selectedCaseId={selectedCaseId}
            onCaseIdChange={setSelectedCaseId}
            onSubmitSuccess={handleQuickSubmit}
            formSeed={formSeed}
            onFormSeedConsumed={clearFormSeed}
          />

          <section aria-labelledby="attention-heading">
            <div className="mb-3 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-red-500" aria-hidden />
              <h3 id="attention-heading" className="text-lg font-semibold text-slate-900">
                Attention required
              </h3>
            </div>
            <p className="mb-4 text-sm text-slate-500">Missing and pending logs that need action first.</p>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {dailyLogsData.attentionRequired.map((item) => (
                <AttentionCard key={item.id} item={item} onCompleteLog={handleCompleteAttention} />
              ))}
            </div>
          </section>

          <section aria-labelledby="recent-heading">
            <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-amber-400" aria-hidden />
                  <h3 id="recent-heading" className="text-lg font-semibold text-slate-900">
                    Recent logs
                  </h3>
                </div>
                <p className="mt-1 text-sm text-slate-500">Card view — fastest to scan on mobile.</p>
              </div>
              <FilterBar value={statusFilter} onChange={setStatusFilter} />
            </div>

            {emptyFiltered ? (
              <div className="rounded-2xl border border-dashed border-[#E2E8F0] bg-white px-6 py-16 text-center shadow-sm">
                <p className="text-lg font-semibold text-slate-800">
                  {noLogsAtAll && !search.trim() && statusFilter === 'all'
                    ? 'No logs yet today — start your first session'
                    : 'No logs match your filters'}
                </p>
                <p className="mt-2 text-sm text-slate-500">
                  {noLogsAtAll && !search.trim() && statusFilter === 'all'
                    ? 'Use Quick log above or the floating button on your phone.'
                    : 'Try clearing search or switching status.'}
                </p>
                <button
                  type="button"
                  onClick={handleNewLog}
                  className="mt-6 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
                >
                  Start Quick log
                </button>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {filteredLogs.map((log) => (
                  <LogCard
                    key={log.id}
                    log={log}
                    onView={() => showToast(`Opening ${log.caseId} (demo)`)}
                    onEdit={() => {
                      setSelectedCaseId(log.caseId)
                      scrollToQuickLog()
                    }}
                    onDuplicate={handleDuplicate}
                  />
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="min-w-0 xl:sticky xl:top-4 xl:self-start">
          <ChecklistPanel items={checklist} onToggle={handleCheckToggle} />
        </div>
      </div>

      <button
        type="button"
        onClick={handleNewLog}
        className="fixed bottom-6 right-5 z-50 flex h-14 items-center gap-2 rounded-full bg-indigo-600 px-5 text-sm font-bold text-white shadow-[0_8px_30px_rgba(79,70,229,0.45)] transition hover:scale-[1.03] hover:bg-indigo-700 xl:hidden"
        aria-label="Quick log"
      >
        + Quick log
      </button>
    </div>
  )
}
