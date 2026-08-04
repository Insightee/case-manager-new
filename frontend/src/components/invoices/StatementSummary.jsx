import { ConfidenceBadge } from '../admin-portal/ui/ConfidenceBadge.jsx'
import { formatInr, statementConfidence, statementLadder } from './invoiceUtils.js'

function amountCell(row) {
  if (row.amount == null) {
    return <span className="text-xs italic text-slate-400">{row.note}</span>
  }
  const sign = row.kind === 'deduction' ? '−' : ''
  const tone =
    row.kind === 'net'
      ? 'font-bold text-indigo-900'
      : row.kind === 'deduction'
        ? 'font-semibold text-rose-700'
        : 'font-semibold text-slate-900'
  return <span className={`tabular-nums ${tone}`}>{`${sign}${formatInr(row.amount)}`}</span>
}

/**
 * Therapist's monthly statement — system-generated from the payout engine.
 * The therapist re-types nothing; they review then approve or dispute. Client
 * pricing never reaches here (redacted at the API boundary).
 */
export function StatementSummary({ data, cutover = false }) {
  if (!data) return null
  const rows = statementLadder(data)
  const confidence = statementConfidence(data, { cutover })

  return (
    <section className="rounded-xl border border-[#E2E8F0] bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800">
          Monthly statement — {data.month_label || data.month}
        </h3>
        <ConfidenceBadge
          confidence={confidence}
          reason={cutover ? undefined : 'Provisional until finance reconciles this payout.'}
        />
      </div>

      <dl className="mt-3 divide-y divide-[#F1F5F9]">
        {rows.map((row) => (
          <div
            key={row.key}
            className={`flex items-center justify-between py-2 text-sm ${
              row.kind === 'net' ? 'border-t border-[#E2E8F0] pt-3' : ''
            }`}
          >
            <dt className={row.kind === 'net' ? 'font-semibold text-indigo-900' : 'text-slate-600'}>
              {row.label}
            </dt>
            <dd>{amountCell(row)}</dd>
          </div>
        ))}
      </dl>

      <p className="mt-3 text-xs text-slate-500">
        System-generated from your approved sessions — you don’t enter any figures. Review and approve, or
        dispute a line.
      </p>
    </section>
  )
}
