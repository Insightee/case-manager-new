import { useMemo, useState } from 'react'
import { formatInr } from './invoiceUtils.js'
import { StatusBadge } from './StatusBadge.jsx'
import {
  applyLedgerFilters,
  clientOptionsFromFilters,
  computeFilteredSummary,
  defaultLedgerFilters,
  ledgerStatusKey,
  monthOptionsFromFilters,
  statusOptionsFromFilters,
  yearOptionsFromFilters,
} from '../../lib/ledgerUtils.js'

function formatSubmitted(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return '—'
  }
}

function FilterSelect({ label, value, onChange, options, allLabel }) {
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1 sm:max-w-[180px]">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-h-[44px] w-full rounded-xl border border-[#E2E8F0] bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15"
      >
        <option value="">{allLabel}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function LedgerSummaryStrip({ summary }) {
  if (!summary?.rowCount) return null
  const items = [
    { label: 'Statements', value: summary.rowCount },
    { label: 'Sessions', value: summary.sessionCount },
    { label: 'Gross', value: formatInr(summary.grossInr) },
    { label: 'Net payable', value: formatInr(summary.netInr) },
    { label: 'Paid', value: formatInr(summary.paidInr), tone: 'text-emerald-700' },
    { label: 'Pending', value: formatInr(summary.pendingInr), tone: 'text-amber-700' },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl border border-[#E2E8F0] bg-slate-50/80 px-3 py-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{item.label}</p>
          <p className={`mt-0.5 text-sm font-bold tabular-nums text-slate-900 ${item.tone || ''}`}>{item.value}</p>
        </div>
      ))}
    </div>
  )
}

export function StatementLedger({
  rows = [],
  filterOptions,
  loading,
  onView,
  onDownloadPayslip,
  downloadingId,
  embedded = false,
}) {
  const [filters, setFilters] = useState(defaultLedgerFilters)

  const yearOptions = useMemo(() => yearOptionsFromFilters(filterOptions), [filterOptions])
  const monthOptions = useMemo(() => monthOptionsFromFilters(filterOptions), [filterOptions])
  const clientOptions = useMemo(() => clientOptionsFromFilters(filterOptions), [filterOptions])
  const statusOptions = useMemo(() => statusOptionsFromFilters(filterOptions), [filterOptions])

  const filteredRows = useMemo(() => applyLedgerFilters(rows, filters), [rows, filters])
  const summary = useMemo(() => computeFilteredSummary(filteredRows), [filteredRows])

  const hasActiveFilters = Boolean(filters.year || filters.month || filters.caseId || filters.status)

  const setFilter = (key) => (value) => setFilters((prev) => ({ ...prev, [key]: value }))

  const filterBar = (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <FilterSelect
          label="Year"
          value={filters.year}
          onChange={setFilter('year')}
          options={yearOptions}
          allLabel="All years"
        />
        <FilterSelect
          label="Month"
          value={filters.month}
          onChange={setFilter('month')}
          options={monthOptions}
          allLabel="All months"
        />
        <FilterSelect
          label="Client"
          value={filters.caseId}
          onChange={setFilter('caseId')}
          options={clientOptions}
          allLabel="All clients"
        />
        <FilterSelect
          label="Status"
          value={filters.status}
          onChange={setFilter('status')}
          options={statusOptions}
          allLabel="All statuses"
        />
        {hasActiveFilters ? (
          <button
            type="button"
            onClick={() => setFilters(defaultLedgerFilters())}
            className="min-h-[44px] rounded-xl border border-[#E2E8F0] bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 sm:self-end"
          >
            Clear filters
          </button>
        ) : null}
      </div>
      <LedgerSummaryStrip summary={summary} />
    </div>
  )

  const body = loading ? (
    <p className={`text-center text-sm text-slate-500 ${embedded ? 'px-4 py-8' : 'px-4 py-10 sm:px-5'}`}>
      Loading your statements…
    </p>
  ) : rows.length === 0 ? (
    <p
      className={`text-center text-sm text-slate-500 ${embedded ? 'rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8' : 'px-4 py-10 sm:px-5'}`}
    >
      No submitted statements yet — generate your first invoice to see it here.
    </p>
  ) : filteredRows.length === 0 ? (
    <p className="rounded-xl border border-dashed border-[#E2E8F0] bg-white px-4 py-8 text-center text-sm text-slate-500">
      No statements match these filters. Try clearing a filter or choosing a different period.
    </p>
  ) : (
    <>
      <div className={`hidden overflow-x-auto md:block ${embedded ? 'rounded-xl border border-[#E2E8F0] bg-white' : ''}`}>
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3">Period</th>
              <th className="px-5 py-3">Client</th>
              <th className="px-5 py-3">Submitted</th>
              <th className="px-5 py-3 text-right">Sessions</th>
              <th className="px-5 py-3 text-right">Gross</th>
              <th className="px-5 py-3 text-right">Net payable</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0]">
            {filteredRows.map((inv) => (
              <tr key={inv.id} className="hover:bg-slate-50/80">
                <td className="px-5 py-3 font-medium text-slate-900">{inv.month}</td>
                <td className="max-w-[180px] truncate px-5 py-3 text-slate-700" title={inv.clientLabel}>
                  {inv.clientLabel || '—'}
                </td>
                <td className="px-5 py-3 text-slate-600">{formatSubmitted(inv.createdAt || inv.created_at)}</td>
                <td className="px-5 py-3 text-right tabular-nums text-slate-700">
                  {inv.sessionsCount ?? inv.sessions_count ?? 0}
                </td>
                <td className="px-5 py-3 text-right tabular-nums text-slate-700">
                  {formatInr(inv.subtotalInr ?? inv.subtotal_inr ?? inv.amountInr ?? inv.amount_inr ?? 0)}
                </td>
                <td className="px-5 py-3 text-right tabular-nums font-semibold text-slate-900">
                  {formatInr(inv.amountInr ?? inv.amount_inr ?? 0)}
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

      <div className={`divide-y divide-[#E2E8F0] md:hidden ${embedded ? 'rounded-xl border border-[#E2E8F0] bg-white' : ''}`}>
        {filteredRows.map((inv) => (
          <article key={inv.id} className="px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-slate-900">{inv.month}</p>
                <p className="mt-0.5 truncate text-xs text-slate-600">{inv.clientLabel || '—'}</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Submitted {formatSubmitted(inv.createdAt || inv.created_at)}
                </p>
              </div>
              <StatusBadge status={ledgerStatusKey(inv.status)} />
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt className="text-xs text-slate-500">Sessions</dt>
                <dd className="font-medium tabular-nums text-slate-800">{inv.sessionsCount ?? inv.sessions_count ?? 0}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500">Net payable</dt>
                <dd className="font-semibold tabular-nums text-slate-900">{formatInr(inv.amountInr ?? inv.amount_inr ?? 0)}</dd>
              </div>
            </dl>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-lg border border-[#E2E8F0] bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                onClick={() => onView?.(inv)}
              >
                View breakdown
              </button>
              <button
                type="button"
                className="min-h-[44px] flex-1 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-900 disabled:opacity-60"
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
  )

  if (embedded) {
    return (
      <div className="space-y-4">
        {filterBar}
        {body}
      </div>
    )
  }

  return (
    <section aria-labelledby="statement-ledger-title" className="rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
      <header className="border-b border-[#E2E8F0] px-4 py-4 sm:px-5">
        <h3 id="statement-ledger-title" className="text-lg font-semibold text-slate-900">
          Statement ledger
        </h3>
        <p className="mt-1 text-sm text-slate-500">
          Filter by year, month, client, or status — then view breakdowns or download payslips.
        </p>
      </header>
      <div className="space-y-4 px-4 py-4 sm:px-5">{filterBar}</div>
      {body}
    </section>
  )
}
