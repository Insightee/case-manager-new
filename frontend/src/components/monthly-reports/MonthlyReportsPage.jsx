import { useCallback, useMemo, useState } from 'react'
import monthlyData from '../../data/monthlyReports.json'
import { CalendarModal } from './CalendarModal.jsx'
import { ChecklistPanel } from './ChecklistPanel.jsx'
import { PipelineStats } from './PipelineStats.jsx'
import { ReportCard } from './ReportCard.jsx'
import { SectionHeader } from './SectionHeader.jsx'

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
        <p className="font-semibold text-slate-900">Done</p>
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

function matchesSearch(item, q) {
  if (!q.trim()) return true
  const s = q.toLowerCase()
  return (
    item.caseId.toLowerCase().includes(s) ||
    item.child.toLowerCase().includes(s) ||
    item.month.toLowerCase().includes(s)
  )
}

function SectionBlock({ id, title, subtitle, dotClass, children }) {
  return (
    <section aria-labelledby={id}>
      <div className="mb-3 flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${dotClass}`} aria-hidden />
        <h3 id={id} className="text-lg font-semibold text-slate-900">
          {title}
        </h3>
      </div>
      {subtitle && <p className="mb-4 text-sm text-slate-500">{subtitle}</p>}
      {children}
    </section>
  )
}

export function MonthlyReportsPage() {
  const [search, setSearch] = useState('')
  const [pipelineFilter, setPipelineFilter] = useState('all')
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [checklist, setChecklist] = useState(monthlyData.checklist.map((c) => ({ ...c })))
  const [toast, setToast] = useState({ visible: false, message: '' })

  const showToast = useCallback((message) => {
    setToast({ visible: true, message })
    window.setTimeout(() => setToast((t) => ({ ...t, visible: false })), 3800)
  }, [])

  const handlePipelineClick = useCallback((key) => {
    setPipelineFilter((prev) => (prev === key ? 'all' : key))
  }, [])

  const q = search.trim()

  const filteredAttention = useMemo(() => {
    let list = monthlyData.attention.filter((a) => matchesSearch(a, q))
    if (pipelineFilter === 'overdue') list = list.filter((a) => a.attentionType === 'overdue')
    return list
  }, [q, pipelineFilter])

  const filteredInProgress = useMemo(() => {
    let list = monthlyData.inProgress.filter((r) => matchesSearch(r, q))
    if (pipelineFilter === 'draft') list = list.filter((r) => r.status === 'draft')
    if (pipelineFilter === 'underReview') list = list.filter((r) => r.status === 'under_review')
    return list
  }, [q, pipelineFilter])

  const filteredPublished = useMemo(() => {
    return monthlyData.published.filter((r) => matchesSearch(r, q))
  }, [q])

  const showAttentionSection = pipelineFilter === 'all' || pipelineFilter === 'overdue'
  const showProgressSection =
    pipelineFilter === 'all' || pipelineFilter === 'draft' || pipelineFilter === 'underReview'
  const showPublishedSection = pipelineFilter === 'all' || pipelineFilter === 'published'

  const totalVisible = useMemo(() => {
    let n = 0
    if (showAttentionSection) n += filteredAttention.length
    if (showProgressSection) n += filteredInProgress.length
    if (showPublishedSection) n += filteredPublished.length
    return n
  }, [
    showAttentionSection,
    showProgressSection,
    showPublishedSection,
    filteredAttention.length,
    filteredInProgress.length,
    filteredPublished.length,
  ])

  const activePipelineKey = pipelineFilter === 'all' ? null : pipelineFilter

  const handleCheckToggle = (id) => {
    setChecklist((prev) => prev.map((i) => (i.id === id ? { ...i, done: !i.done } : i)))
  }

  const handleGenerate = useCallback(
    (report) => {
      showToast(
        `Draft generated from daily logs & session summaries for ${report.caseId} (${report.month}).`,
      )
    },
    [showToast],
  )

  const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })

  return (
    <div className="relative flex min-h-full flex-col gap-6 rounded-2xl bg-[#F8FAFC] px-1 py-2 pb-28 sm:px-3 sm:py-4 lg:pb-8">
      <Toast
        message={toast.message}
        visible={toast.visible}
        onDismiss={() => setToast((t) => ({ ...t, visible: false }))}
      />

      <CalendarModal
        open={calendarOpen}
        onClose={() => setCalendarOpen(false)}
        events={monthlyData.calendarEvents}
      />

      <SectionHeader
        title="Monthly Reports"
        subtitle="Compile, review, and publish month-end reports"
        search={search}
        onSearchChange={setSearch}
        primaryActionLabel="+ Create Draft"
        onPrimaryAction={() => {
          scrollTop()
          showToast('New draft created — pick a case to continue.')
        }}
        secondaryActionLabel="View Calendar"
        onSecondaryAction={() => setCalendarOpen(true)}
      />

      {pipelineFilter !== 'all' && (
        <button
          type="button"
          onClick={() => setPipelineFilter('all')}
          className="self-start rounded-full border border-[#E2E8F0] bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50"
        >
          Clear pipeline filter
        </button>
      )}

      <section aria-label="Pipeline overview">
        <h3 className="sr-only">Report pipeline overview</h3>
        <PipelineStats
          counts={{
            draft: monthlyData.pipeline.draft,
            underReview: monthlyData.pipeline.underReview,
            published: monthlyData.pipeline.published,
            overdue: monthlyData.pipeline.overdue,
          }}
          activeFilter={activePipelineKey}
          onFilter={handlePipelineClick}
        />
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-8">
          {totalVisible === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#E2E8F0] bg-white px-6 py-16 text-center shadow-sm">
              <p className="text-lg font-semibold text-slate-800">
                {q || pipelineFilter !== 'all'
                  ? 'No reports match your search or filters'
                  : 'No reports yet — generate your first report from logs'}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                {q || pipelineFilter !== 'all'
                  ? 'Try clearing the pipeline filter or widening your search.'
                  : 'Use Create Draft or generate from logs on any case card.'}
              </p>
              <button
                type="button"
                onClick={() => showToast('Opening draft composer…')}
                className="mt-6 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
              >
                Generate from logs
              </button>
            </div>
          ) : (
            <>
          {showAttentionSection && (
            <SectionBlock
              id="attention-heading"
              title="Attention required"
              subtitle="Overdue, not started, and rejected — act first."
              dotClass="bg-red-500"
            >
              {filteredAttention.length === 0 ? (
                <p className="rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8 text-center text-sm text-slate-500">
                  Nothing urgent in this view.
                </p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {filteredAttention.map((r) => (
                    <ReportCard
                      key={r.id}
                      variant="attention"
                      report={r}
                      onGenerateFromLogs={handleGenerate}
                      onStart={(rep) => showToast(`Starting report for ${rep.caseId}…`)}
                      onContinue={(rep) => showToast(`Opening editor for ${rep.caseId}…`)}
                    />
                  ))}
                </div>
              )}
            </SectionBlock>
          )}

          {showProgressSection && (
            <SectionBlock
              id="in-progress-heading"
              title="In progress"
              subtitle="Drafts and items under review — recently edited first."
              dotClass="bg-amber-400"
            >
              {filteredInProgress.length === 0 ? (
                <p className="rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8 text-center text-sm text-slate-500">
                  No reports in this stage for the current filter.
                </p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {filteredInProgress.map((r) => (
                    <ReportCard
                      key={r.id}
                      variant="progress"
                      report={r}
                      onGenerateFromLogs={handleGenerate}
                      onContinue={(rep) => showToast(`Continue editing ${rep.caseId}…`)}
                      onPreview={(rep) => showToast(`Preview ${rep.caseId} (demo)`)}
                      onSubmitReview={(rep) => showToast(`Submitted ${rep.caseId} for review.`)}
                    />
                  ))}
                </div>
              )}
            </SectionBlock>
          )}

          {showPublishedSection && (
            <SectionBlock
              id="published-heading"
              title="Published"
              subtitle="Compact archive — view or download."
              dotClass="bg-emerald-500"
            >
              {filteredPublished.length === 0 ? (
                <p className="rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8 text-center text-sm text-slate-500">
                  No published reports match your search.
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredPublished.map((r) => (
                    <ReportCard
                      key={r.id}
                      variant="published"
                      report={r}
                      onGenerateFromLogs={handleGenerate}
                      onView={(rep) => showToast(`Opening ${rep.caseId} published report…`)}
                      onDownload={(rep) => showToast(`Downloading PDF for ${rep.caseId}…`)}
                    />
                  ))}
                </div>
              )}
            </SectionBlock>
          )}
            </>
          )}
        </div>

        <div className="min-w-0 xl:sticky xl:top-4 xl:self-start">
          <ChecklistPanel items={checklist} onToggle={handleCheckToggle} />
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          scrollTop()
          showToast('Create a new report — choose a case when the composer opens.')
        }}
        className="fixed bottom-6 right-5 z-50 flex h-14 items-center gap-2 rounded-full bg-indigo-600 px-5 text-sm font-bold text-white shadow-[0_8px_30px_rgba(79,70,229,0.45)] transition hover:scale-[1.03] hover:bg-indigo-700 xl:hidden"
        aria-label="Create report"
      >
        + Create Report
      </button>
    </div>
  )
}
