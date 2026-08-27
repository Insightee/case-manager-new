import { useState } from 'react'
import { isLeaveBalanceUpdated, leaveBalanceRemainingLabel } from '../../lib/leaveBalanceDisplay.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import {
  billingSummary,
  formatCaseAttendanceStrip,
  formatInr,
  formatModalHeaderSummary,
  lineTypeLabel,
} from './invoiceUtils.js'
import { AddLateSessionForm } from './AddLateSessionForm.jsx'

function SessionRow({ line, editable, onToggle, onRemove, pending, tagLabel }) {
  const excluded = line.included === false && !pending
  const tag = tagLabel || line.flags?.pending_reason
  return (
    <tr className={excluded ? 'opacity-50' : ''}>
      <td className="py-2 pr-3 text-sm text-slate-700">{formatDisplayDate(line.session_date)}</td>
      <td className="py-2 pr-3 text-sm text-slate-600">{line.duration_minutes ?? 60} min</td>
      <td className="py-2 pr-3 text-xs text-slate-500">
        {line.ui_label || lineTypeLabel(line.line_type)}
        {tag ? (
          <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 font-semibold text-amber-800">{tag}</span>
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
            key={line.session_id ?? line.id ?? line.absence_request_id ?? `line-${idx}`}
            line={line}
            editable={editable}
            pending={pending}
            tagLabel={line.flags?.pending_reason}
            onToggle={onToggle}
            onRemove={onRemove}
          />
        ))}
      </tbody>
    </table>
  )
}

function AttendanceSummary({ data }) {
  const summary = data.attendance_summary
  const headerGist = formatModalHeaderSummary(summary)
  const hasCalendarLeave = summary?.paid_leaves != null || summary?.unpaid_leaves != null
  const hasSessionLeave = summary?.leave_taken != null

  return (
    <div className="space-y-2 rounded-xl border border-[#E2E8F0] bg-slate-50/80 p-4">
      {headerGist ? (
        <p className="text-sm font-medium text-slate-700">{headerGist}</p>
      ) : null}
      {hasCalendarLeave ? (
        <p className="text-xs text-slate-600">
          Paid leaves: {summary.paid_leaves ?? 0} · Unpaid leaves: {summary.unpaid_leaves ?? 0}
        </p>
      ) : null}
      {hasSessionLeave ? (
        <p className="text-xs text-slate-600">
          Leave taken: {summary.leave_taken ?? 0}
          <span className="ml-2 text-slate-500">Payout is based on sessions done this month.</span>
        </p>
      ) : null}
      <div className="grid gap-3 pt-2 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Subtotal (approved)</p>
          <p className="text-lg font-bold text-slate-900">{formatInr(data.subtotal_inr)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Leave deduction</p>
          <p className="text-lg font-bold text-rose-700">−{formatInr(data.leave_deduction_inr)}</p>
          <p className="text-[10px] text-slate-500">Leave deduction stays fixed when you exclude sessions.</p>
        </div>
        {(data.pending_approval_count ?? data.pending_late_count ?? 0) > 0 ? (
          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase text-amber-700">Pending approval</p>
            <p className="text-sm font-bold text-amber-900">
              {data.pending_approval_count ?? data.pending_late_count} item
              {(data.pending_approval_count ?? data.pending_late_count) === 1 ? '' : 's'} ·{' '}
              {formatInr(data.pending_approval_inr ?? data.pending_late_inr)} excluded from payout
            </p>
          </div>
        ) : null}
        <div className="border-t border-[#E2E8F0] pt-3 sm:col-span-2">
          <p className="text-xs font-semibold uppercase text-indigo-600">Net payout</p>
          <p className="text-2xl font-bold text-indigo-900">{formatInr(data.net_amount_inr ?? data.amount_inr)}</p>
        </div>
      </div>
    </div>
  )
}

function RejectedNotes({ notes }) {
  const [open, setOpen] = useState(false)
  if (!notes?.length) return null
  return (
    <section className="rounded-xl border border-slate-200 bg-slate-50/60">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-800"
        onClick={() => setOpen((v) => !v)}
      >
        <span>Not included ({notes.length})</span>
        <span className="text-xs text-slate-500">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open ? (
        <div className="border-t border-slate-200 px-4 py-3">
          <p className="mb-2 text-xs text-slate-600">These were turned down and are not part of this payout.</p>
          <ul className="space-y-2 text-sm text-slate-700">
            {notes.map((note, idx) => (
              <li key={`${note.type}-${note.date}-${idx}`} className="rounded-lg border border-[#E2E8F0] bg-white px-3 py-2">
                {formatDisplayDate(note.date)}
                {note.case_code ? ` · ${note.case_code}` : ''}
                {note.child_name ? ` · ${note.child_name}` : ''}
                {note.reason ? ` · ${note.reason}` : ''}
                {note.status ? <span className="text-slate-500"> · {note.status}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

export function InvoiceBreakdownView({
  data,
  editable,
  month,
  onToggleSession,
  onRefresh,
  onRemoveLateSession,
  hideSummary = false,
}) {
  const [summaryOpen, setSummaryOpen] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 640px)').matches : true,
  )

  if (!data) {
    return <p className="text-sm text-slate-500">No breakdown available.</p>
  }

  const leaveBalance = data.leave_balance
  const rejectedNotes = data.rejected_notes || []

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

      {!hideSummary ? (
        <section>
          <button
            type="button"
            className="mb-2 flex w-full items-center justify-between text-left sm:hidden"
            onClick={() => setSummaryOpen((v) => !v)}
          >
            <span className="text-sm font-semibold text-slate-800">Payout summary</span>
            <span className="text-xs text-slate-500">{summaryOpen ? 'Collapse' : 'Expand'}</span>
          </button>
          <div className={summaryOpen ? 'block' : 'hidden sm:block'}>
            <AttendanceSummary data={data} />
          </div>
        </section>
      ) : null}

      {(data.cases || []).map((caseGroup) => {
        const displayIncluded =
          caseGroup.display_included_sessions ?? caseGroup.included_sessions ?? 0
        const pendingLines =
          caseGroup.pending_approval_lines || caseGroup.pending_late_lines || []
        const absenceLines = (caseGroup.child_absence_lines || []).filter((l) => l.included)
        const pendingAbsenceLines = (caseGroup.child_absence_lines || []).filter((l) => !l.included)
        const hasActivity = caseGroup.has_activity !== false && (
          caseGroup.has_activity ||
          (caseGroup.session_lines?.length || 0) > 0 ||
          pendingLines.length > 0 ||
          (caseGroup.child_absence_lines?.length || 0) > 0
        )
        const attendanceStrip = hasActivity
          ? formatCaseAttendanceStrip(caseGroup.attendance, caseGroup.billing_profile)
          : null

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
              {attendanceStrip ? (
                <p className="mt-1 text-xs font-medium text-slate-600">{attendanceStrip}</p>
              ) : null}
              <p className="mt-2 text-sm font-bold text-indigo-900">
                Case total: {formatInr(caseGroup.therapist_share_inr)}
                {hasActivity ? (
                  <span className="ml-2 font-normal text-slate-600">
                    ({displayIncluded} session{displayIncluded === 1 ? '' : 's'} in payout
                    {caseGroup.additional_sessions ? `, ${caseGroup.additional_sessions} extra` : ''})
                  </span>
                ) : null}
              </p>
              {pendingLines.length > 0 ? (
                <p className="mt-1 text-xs font-semibold text-amber-800">
                  + {formatInr(caseGroup.pending_approval_inr ?? caseGroup.pending_late_inr)} pending approval
                </p>
              ) : null}
            </header>
            <div className="overflow-x-auto px-4 py-2">
              <SessionTable
                lines={caseGroup.session_lines}
                editable={editable}
                onToggle={onToggleSession ? (line) => onToggleSession(caseGroup.case_id, line) : undefined}
              />
              {absenceLines.length > 0 ? (
                <div className="mt-4 border-t border-indigo-100 pt-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-indigo-800">Child absence</p>
                  <SessionTable lines={absenceLines} editable={false} />
                </div>
              ) : null}
              {pendingLines.length > 0 || pendingAbsenceLines.length > 0 ? (
                <div className="mt-4 border-t border-amber-100 pt-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-amber-800">Pending approval</p>
                  <SessionTable
                    lines={[...pendingLines, ...pendingAbsenceLines]}
                    editable={editable}
                    pending
                    onRemove={
                      onRemoveLateSession
                        ? (line) => line.session_id && onRemoveLateSession(line.session_id)
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

      <RejectedNotes notes={rejectedNotes} />
    </div>
  )
}
