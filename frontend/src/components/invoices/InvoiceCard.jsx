import { StatusBadge } from './StatusBadge.jsx'

function formatInr(n) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n)
}

function ActionBtn({ children, variant = 'neutral', ...props }) {
  const styles = {
    neutral: 'border-[#E2E8F0] bg-white text-slate-700 hover:bg-slate-50',
    primary: 'border-indigo-200 bg-indigo-50 text-indigo-800 hover:bg-indigo-100',
    accent: 'border-orange-200 bg-orange-50 text-orange-900 hover:bg-orange-100',
    danger: 'border-red-200 bg-red-50 text-red-900 hover:bg-red-100',
  }
  return (
    <button
      type="button"
      className={`min-h-[40px] rounded-lg px-3 py-2 text-sm font-semibold shadow-sm ring-1 transition ${styles[variant]}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function InvoiceCard({
  variant,
  invoice,
  onResolve,
  onViewDetails,
  onDownloadCsv,
  onView,
  onDownloadPdf,
}) {
  const base =
    'rounded-2xl border border-[#E2E8F0] bg-white p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)] transition-transform duration-200 hover:scale-[1.01] hover:shadow-[0_12px_32px_rgba(15,23,42,0.08)]'

  if (variant === 'attention') {
    const urgent =
      invoice.status === 'rejected'
        ? 'border-red-200 bg-gradient-to-br from-red-50/95 to-white'
        : 'border-amber-200 bg-gradient-to-br from-amber-50/95 to-white'

    return (
      <article className={`${base} ${urgent}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">{invoice.month}</p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">{formatInr(invoice.amountINR)}</p>
            <StatusBadge status={invoice.status === 'rejected' ? 'rejected' : 'queried'} />
          </div>
          <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-bold uppercase text-orange-800 ring-1 ring-orange-200">
            {invoice.message || 'Fix required'}
          </span>
        </div>
        {invoice.detail && <p className="mt-3 text-sm text-slate-600">{invoice.detail}</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          <ActionBtn variant="danger" onClick={() => onResolve?.(invoice)}>
            Resolve issue
          </ActionBtn>
          <ActionBtn variant="primary" onClick={() => onViewDetails?.(invoice)}>
            View details
          </ActionBtn>
        </div>
      </article>
    )
  }

  if (variant === 'progress') {
    return (
      <article className={base}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">{invoice.month}</p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">{formatInr(invoice.amountINR)}</p>
            <p className="mt-2 text-sm text-slate-600">
              <span className="font-semibold text-slate-800">{invoice.sessions}</span> sessions / logs
            </p>
            {invoice.subtitle && <p className="mt-1 text-xs text-slate-500">{invoice.subtitle}</p>}
          </div>
          <StatusBadge status="in_review" />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <ActionBtn variant="primary" onClick={() => onViewDetails?.(invoice)}>
            View details
          </ActionBtn>
          <ActionBtn variant="neutral" onClick={() => onDownloadCsv?.(invoice)}>
            Download CSV
          </ActionBtn>
        </div>
      </article>
    )
  }

  if (variant === 'paid') {
    return (
      <article className={`${base} p-3 sm:p-4`}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{invoice.month}</p>
            <p className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 sm:text-xl">{formatInr(invoice.amountINR)}</p>
            <p className="mt-1 text-xs text-slate-500">
              Paid <span className="font-medium text-slate-700">{invoice.paidDate}</span>
            </p>
          </div>
          <StatusBadge status="paid" />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <ActionBtn variant="primary" onClick={() => onView?.(invoice)}>
            View
          </ActionBtn>
          <ActionBtn variant="neutral" onClick={() => onDownloadPdf?.(invoice)}>
            Download PDF
          </ActionBtn>
        </div>
      </article>
    )
  }

  return null
}
