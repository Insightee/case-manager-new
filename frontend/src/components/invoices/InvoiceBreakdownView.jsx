import { isLeaveBalanceUpdated, leaveBalanceRemainingLabel } from '../../lib/leaveBalanceDisplay.js'
import { billingSummary, formatInr, lineTypeLabel } from './invoiceUtils.js'
import { AddLateSessionForm } from './AddLateSessionForm.jsx'

function SessionRow({ line, editable, onToggle, onRemove, pending }) {
  const excluded = line.included === false && !pending
  const late = line.flags?.added_late || pending
  return (
    <tr className={excluded ? 'opacity-50' : ''}>
      <td className="py-2 pr-3 text-sm text-slate-700">{line.session_date}</td>
      <td className="py-2 pr-3 text-sm text-slate-600">{line.duration_minutes ?? 60} min</td>
      <td className="py-2 pr-3 text-xs text-slate-500">
        {lineTypeLabel(line.line_type)}
        {late ? (
          <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 font-semibold text-amber-800">Added late</span>
        ) : null}
        {pending ? (
          <span className="ml-1 rounded bg-amber-200 px-1.5 py-0.5 font-semibold text-amber-900">Pending approval</span>
        ) : null}
      </td>
      <td className="py-2 pr-3 text-right text-sm font-semibold tabular-nums text-slate-900">
        {formatInr(line.amount_inr)}
        {pending ? <span className="block text-[10px] font-normal text-amber-800">Excluded from payout</span> : null}
      </td>
      {editable ? (
        <td className="py-2 text-right">
          {pending && onRemove ? (
            <button type="button" className="text-xs font-semibold text-rose-600 hover:text-rose-800" onClick={() => onRemove(line)}>
              Remove
            </button>
          ) : (
            <button
              type="button"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
              onClick={() => onToggle?.(line)}
            >
              {excluded ? 'Include' : 'Exclude'}
            </button>
          )}
        </td>
      ) : null}
    </tr>
  )
}

function SessionTable({ lines, editable, onToggle, onRemove, pending }) {
  if (!lines?.length) return null
  return (
    <table className="w-full min-w-[480px]">
      <thead>
        <tr className="text-left text-xs font-semibold uppercase text-slate-500">
          <th className="pb-2 pr-3">Date</th>
          <th className="pb-2 pr-3">Duration</th>
          <th className="pb-2 pr-3">Type</th>
          <th className="pb-2 pr-3 text-right">Amount</th>
          {editable ? <th className="pb-2 text-right">Action</th> : null}
        </tr>
      </thead>
      <tbody>
        {lines.map((line, idx) => (
          <SessionRow
            key={line.session_id ?? line.id ?? `line-${idx}`}
            line={line}
            editable={editable}
            pending={pending}
            onToggle={onToggle}
            onRemove={onRemove}
          />
        ))}
      </tbody>
    </table>
  )
}

export function InvoiceBreakdownView({
  data,
  editable,
  month,
  onToggleSession,
  onRefresh,
  onRemoveLateSession,
}) {
  if (!data) {
    return <p className="text-sm text-slate-500">No breakdown available.</p>
  }

  const leaveDetails = data.leave_details || []
  const leaveBalance = data.leave_balance
  const pendingCount = data.pending_late_count ?? 0

  return (
    <div className="space-y-6">
      {leaveBalance ? (
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 text-sm text-slate-700">
          <p className="text-xs font-semibold uppercase text-indigo-700">Leave balance ({leaveBalance.year})</p>
          <p className="mt-1">
            Paid remaining: <strong>{leaveBalanceRemainingLabel(leaveBalance)}</strong>
            {!isLeaveBalanceUpdated(leaveBalance) ? (
              <span className="ml-2 font-semibold text-amber-700">To be updated</span>
            ) : (
              <>
                {' · '}
                Used: {leaveBalance.paid_used_effective} (system {leaveBalance.computed_paid_used}
                {leaveBalance.backfill_paid_used > 0 ? ` + HR backfill ${leaveBalance.backfill_paid_used}` : ''})
              </>
            )}
          </p>
        </div>
      ) : null}
      <div className="grid gap-3 rounded-xl border border-[#E2E8F0] bg-slate-50/80 p-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Subtotal (approved)</p>
          <p className="text-lg font-bold text-slate-900">{formatInr(data.subtotal_inr)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Leave deduction</p>
          <p className="text-lg font-bold text-rose-700">−{formatInr(data.leave_deduction_inr)}</p>
        </div>
        {pendingCount > 0 ? (
          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase text-amber-700">Pending late sessions</p>
            <p className="text-sm font-bold text-amber-900">
              {pendingCount} session{pendingCount === 1 ? '' : 's'} · {formatInr(data.pending_late_inr)} excluded from payout
            </p>
          </div>
        ) : null}
        <div className="border-t border-[#E2E8F0] pt-3 sm:col-span-2">
          <p className="text-xs font-semibold uppercase text-indigo-600">Net payout</p>
          <p className="text-2xl font-bold text-indigo-900">{formatInr(data.net_amount_inr ?? data.amount_inr)}</p>
        </div>
      </div>

      {leaveDetails.length > 0 ? (
        <section>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Leave impact</h4>
          <ul className="space-y-2 text-sm text-slate-600">
            {leaveDetails.map((l) => (
              <li key={l.leave_id} className="rounded-lg border border-[#E2E8F0] bg-white px-3 py-2">
                {l.start_date} – {l.end_date} · {l.status}
                {l.deduction_inr > 0 ? (
                  <span className="font-semibold text-rose-700"> · −{formatInr(l.deduction_inr)}</span>
                ) : (
                  <span className="text-emerald-700"> · {l.note}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {(data.cases || []).map((caseGroup) => {
        const displayIncluded =
          caseGroup.display_included_sessions ?? caseGroup.included_sessions ?? 0
        const pendingLines = caseGroup.pending_late_lines || []

        return (
          <section key={caseGroup.case_id} className="overflow-hidden rounded-xl border border-[#E2E8F0] bg-white">
            <header className="border-b border-[#E2E8F0] bg-indigo-50/50 px-4 py-3">
              <p className="font-semibold text-slate-900">
                {caseGroup.case_code}
                {caseGroup.child_name ? ` · ${caseGroup.child_name}` : ''}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {billingSummary(caseGroup.billing || caseGroup.billing_snapshot)}
              </p>
              <p className="mt-2 text-sm font-bold text-indigo-900">
                Case total: {formatInr(caseGroup.therapist_share_inr)}
                <span className="ml-2 font-normal text-slate-600">
                  ({displayIncluded} session{displayIncluded === 1 ? '' : 's'} in payout
                  {caseGroup.additional_sessions ? `, ${caseGroup.additional_sessions} extra` : ''})
                </span>
              </p>
              {pendingLines.length > 0 ? (
                <p className="mt-1 text-xs font-semibold text-amber-800">
                  + {formatInr(caseGroup.pending_late_inr)} pending approval
                </p>
              ) : null}
            </header>
            <div className="overflow-x-auto px-4 py-2">
              <SessionTable
                lines={caseGroup.session_lines}
                editable={editable}
                onToggle={onToggleSession ? (line) => onToggleSession(caseGroup.case_id, line) : undefined}
              />
              {pendingLines.length > 0 ? (
                <div className="mt-4 border-t border-amber-100 pt-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-amber-800">Pending approval</p>
                  <SessionTable
                    lines={pendingLines}
                    editable={editable}
                    pending
                    onRemove={
                      onRemoveLateSession
                        ? (line) => onRemoveLateSession(line.session_id)
                        : undefined
                    }
                  />
                </div>
              ) : null}
              {editable && month ? (
                <AddLateSessionForm caseId={caseGroup.case_id} month={month} onAdded={onRefresh} />
              ) : null}
            </div>
          </section>
        )
      })}
    </div>
  )
}
