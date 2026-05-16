import { useCallback, useMemo, useState } from 'react'
import invoiceData from '../../data/invoices.json'
import { ChecklistPanel } from './ChecklistPanel.jsx'
import { EarningsTrendChart } from './EarningsTrendChart.jsx'
import { GenerateInvoiceModal } from './GenerateInvoiceModal.jsx'
import { InvoiceCard } from './InvoiceCard.jsx'
import { SectionHeader } from './SectionHeader.jsx'
import { SummaryCard } from './SummaryCard.jsx'

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
        <p className="font-semibold text-slate-900">Success</p>
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
    item.month?.toLowerCase().includes(s) ||
    item.detail?.toLowerCase().includes(s) ||
    item.subtitle?.toLowerCase().includes(s)
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

export function InvoicesPage() {
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [checklist, setChecklist] = useState(invoiceData.checklist.map((c) => ({ ...c })))
  const [toast, setToast] = useState({ visible: false, message: '' })

  const showToast = useCallback((message) => {
    setToast({ visible: true, message })
    window.setTimeout(() => setToast((t) => ({ ...t, visible: false })), 3800)
  }, [])

  const q = search.trim()

  const filteredAttention = useMemo(
    () => invoiceData.attention.filter((x) => matchesSearch(x, q)),
    [q],
  )
  const filteredProgress = useMemo(
    () => invoiceData.inProgress.filter((x) => matchesSearch(x, q)),
    [q],
  )
  const filteredPaid = useMemo(() => invoiceData.paid.filter((x) => matchesSearch(x, q)), [q])

  const totalVisible = filteredAttention.length + filteredProgress.length + filteredPaid.length

  const openGenerate = useCallback(() => setModalOpen(true), [])

  const handleGenerateFromModal = useCallback(
    (opt) => {
      setModalOpen(false)
      showToast(
        `Invoice for ${opt.label} generated from ${opt.sessions} validated logs · ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(opt.payoutINR)}.`,
      )
    },
    [showToast],
  )

  const handleCheckToggle = (id) => {
    setChecklist((prev) => prev.map((i) => (i.id === id ? { ...i, done: !i.done } : i)))
  }

  const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })

  return (
    <div className="relative flex min-h-full flex-col gap-6 rounded-2xl bg-[#F8FAFC] px-1 py-2 pb-28 sm:px-3 sm:py-4 lg:pb-8">
      <Toast
        message={toast.message}
        visible={toast.visible}
        onDismiss={() => setToast((t) => ({ ...t, visible: false }))}
      />

      <GenerateInvoiceModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        options={invoiceData.generateOptions}
        onGenerate={handleGenerateFromModal}
      />

      <SectionHeader
        title="Invoices"
        subtitle="Generate and track payout workflow from validated logs"
        search={search}
        onSearchChange={setSearch}
        primaryActionLabel="+ Generate Invoice"
        onPrimaryAction={openGenerate}
      />

      <SummaryCard summary={invoiceData.summary} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-8">
          <EarningsTrendChart data={invoiceData.earningsTrend} />

          {totalVisible === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#E2E8F0] bg-white px-6 py-16 text-center shadow-sm">
              <p className="text-lg font-semibold text-slate-800">
                {q ? 'No invoices match your search' : 'No invoices yet — generate your first invoice from logs'}
              </p>
              <p className="mt-2 text-sm text-slate-500">
                {q ? 'Try a different query or clear search.' : 'Validated daily logs are used to calculate your payout.'}
              </p>
              <button
                type="button"
                onClick={openGenerate}
                className="mt-6 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
              >
                Generate invoice
              </button>
            </div>
          ) : (
            <>
              <SectionBlock
                id="attention-inv"
                title="Attention required"
                subtitle="Queried and rejected — resolve before payout can proceed."
                dotClass="bg-red-500"
              >
                {filteredAttention.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8 text-center text-sm text-slate-500">
                    No action items in this view.
                  </p>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {filteredAttention.map((inv) => (
                      <InvoiceCard
                        key={inv.id}
                        variant="attention"
                        invoice={inv}
                        onResolve={(i) => showToast(`Opening resolution for ${i.month}…`)}
                        onViewDetails={(i) => showToast(`Details: ${i.month} (demo)`)}
                      />
                    ))}
                  </div>
                )}
              </SectionBlock>

              <SectionBlock
                id="progress-inv"
                title="In progress"
                subtitle="Recently generated and under finance review."
                dotClass="bg-amber-400"
              >
                {filteredProgress.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8 text-center text-sm text-slate-500">
                    Nothing in review for this search.
                  </p>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {filteredProgress.map((inv) => (
                      <InvoiceCard
                        key={inv.id}
                        variant="progress"
                        invoice={inv}
                        onViewDetails={(i) => showToast(`Opening ${i.month} invoice…`)}
                        onDownloadCsv={(i) => showToast(`Downloading CSV for ${i.month}…`)}
                      />
                    ))}
                  </div>
                )}
              </SectionBlock>

              <SectionBlock
                id="paid-inv"
                title="Paid"
                subtitle="Settled payouts — view receipt or PDF."
                dotClass="bg-emerald-500"
              >
                {filteredPaid.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8 text-center text-sm text-slate-500">
                    No paid invoices match your search.
                  </p>
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredPaid.map((inv) => (
                      <InvoiceCard
                        key={inv.id}
                        variant="paid"
                        invoice={inv}
                        onView={(i) => showToast(`Viewing ${i.month} payment record…`)}
                        onDownloadPdf={(i) => showToast(`Downloading PDF for ${i.month}…`)}
                      />
                    ))}
                  </div>
                )}
              </SectionBlock>
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
          openGenerate()
        }}
        className="fixed bottom-6 right-5 z-50 flex h-14 items-center gap-2 rounded-full bg-[#F97316] px-5 text-sm font-bold text-white shadow-[0_8px_30px_rgba(249,115,22,0.45)] transition hover:scale-[1.03] hover:bg-orange-600 xl:hidden"
        aria-label="Generate invoice"
      >
        + Generate Invoice
      </button>
    </div>
  )
}
