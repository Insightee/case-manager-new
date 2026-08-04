import { formatInr } from './invoiceUtils.js'
import { StatusBadge } from './StatusBadge.jsx'

function formatSubmitted(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return '—'
  }
}

function ledgerStatusKey(apiStatus) {
  const s = String(apiStatus || '').toUpperCase()
  if (s === 'PAID') return 'paid'
  if (s === 'QUERIED') return 'queried'
  if (s === 'REJECTED') return 'rejected'
  if (s === 'APPROVED') return 'approved'
  if (s === 'DRAFT') return 'draft'
  return 'in_review'
}

function sortInvoicesDesc(rows) {
  return [...rows].sort((a, b) => {
    const da = new Date(a.created_at || 0).getTime()
    const db = new Date(b.created_at || 0).getTime()
    if (db !== da) return db - da
    return (b.id || 0) - (a.id || 0)
  })
}

export function StatementLedger({ invoices, loading, onView, onDownloadPayslip, downloadingId }) {
  const rows = sortInvoicesDesc(invoices)

  return (
    <section aria-labelledby="statement-ledger-title" className="rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
      <header className="border-b border-[#E2E8F0] px-4 py-4 sm:px-5">
        <h3 id="statement-ledger-title" className="text-lg font-semibold text-slate-900">
          Statement ledger
        </h3>
        <p className="mt-1 text-sm text-slate-500">
          Previous submitted bills, payout status, and payslip downloads for each month.
        </p>
      </header>

      {loading ? (
        <p className="px-4 py-10 text-center text-sm text-slate-500 sm:px-5">Loading your statements…</p>
      ) : rows.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-slate-500 sm:px-5">
          No submitted statements yet — generate your first invoice to see it here.
        </p>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">Period</th>
                  <th className="px-5 py-3">Submitted</th>
                  <th className="px-5 py-3 text-right">Sessions</th>
                  <th className="px-5 py-3 text-right">Gross</th>
                  <th className="px-5 py-3 text-right">Net payable</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {rows.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50/80">
                    <td className="px-5 py-3 font-medium text-slate-900">{inv.month}</td>
                    <td className="px-5 py-3 text-slate-600">{formatSubmitted(inv.created_at)}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-slate-700">{inv.sessions_count ?? 0}</td>
                    <td className="px-5 py-3 text-right tabular-nums text-slate-700">
                      {formatInr(inv.subtotal_inr ?? inv.amount_inr ?? 0)}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums font-semibold text-slate-900">
                      {formatInr(inv.amount_inr ?? 0)}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={ledgerStatusKey(inv.status)} />
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          className="rounded-lg border border-[#E2E8F0] bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          onClick={() => onView?.(inv)}
                        >
                          View
                        </button>
                        <button
                          type="button"
                          className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-900 hover:bg-emerald-100 disabled:opacity-60"
                          disabled={downloadingId === inv.id}
                          onClick={() => onDownloadPayslip?.(inv)}
                        >
                          {downloadingId === inv.id ? 'Downloading…' : 'Payslip PDF'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="divide-y divide-[#E2E8F0] md:hidden">
            {rows.map((inv) => (
              <article key={inv.id} className="px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-900">{inv.month}</p>
                    <p className="mt-0.5 text-xs text-slate-500">Submitted {formatSubmitted(inv.created_at)}</p>
                  </div>
                  <StatusBadge status={ledgerStatusKey(inv.status)} />
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <dt className="text-xs text-slate-500">Sessions</dt>
                    <dd className="font-medium tabular-nums text-slate-800">{inv.sessions_count ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Net payable</dt>
                    <dd className="font-semibold tabular-nums text-slate-900">{formatInr(inv.amount_inr ?? 0)}</dd>
                  </div>
                </dl>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="min-h-[40px] flex-1 rounded-lg border border-[#E2E8F0] bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                    onClick={() => onView?.(inv)}
                  >
                    View breakdown
                  </button>
                  <button
                    type="button"
                    className="min-h-[40px] flex-1 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-900 disabled:opacity-60"
                    disabled={downloadingId === inv.id}
                    onClick={() => onDownloadPayslip?.(inv)}
                  >
                    {downloadingId === inv.id ? 'Downloading…' : 'Payslip PDF'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
