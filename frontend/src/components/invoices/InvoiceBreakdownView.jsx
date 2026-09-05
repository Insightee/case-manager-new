import { useState } from 'react'
import { invoiceLeaveCreditBanner } from '../../lib/leaveBalanceDisplay.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import {
  isHomecareCaseGroup,
  isShadowCaseGroup,
  lineDisplayAmount,
  lineStatusTag,
  partitionCaseLines,
  formatTherapistHeaderSummary,
  showNextMonthSessionCount,
  nextMonthSessionCount,
} from '../../lib/therapistInvoiceCopy.js'
import {
  billingSummary,
  formatCaseAttendanceStrip,
  formatInr,
  lineTypeLabel,
} from './invoiceUtils.js'
import { AddLateSessionForm } from './AddLateSessionForm.jsx'
import { NextMonthSessionPlanEditor } from './NextMonthSessionPlanEditor.jsx'

function lineKey(line, idx) {
  return line.session_id ?? line.id ?? line.absence_request_id ?? line.leave_id ?? `line-${idx}`
}

function StatusChip({ tag, tone = 'amber' }) {
  if (!tag) return null
  const tones = {
    amber: 'bg-amber-100 text-amber-900',
    green: 'bg-emerald-100 text-emerald-800',
    slate: 'bg-slate-100 text-slate-700',
    rose: 'bg-rose-100 text-rose-800',
  }
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${tones[tone] || tones.amber}`}>
      {tag}
    </span>
  )
}

function SessionLineTags({ line }) {
  const tag = lineStatusTag(line)
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1">
      <span className="text-xs text-slate-600">{line.ui_label || lineTypeLabel(line.line_type)}</span>
      {tag ? <StatusChip tag={tag} tone="amber" /> : null}
    </div>
  )
}

function SessionLineAction({ line, editable, pending, onToggle, onRemove }) {
  if (!editable) return null
  const excluded = line.included === false && !pending
  if (pending && onRemove && line.flags?.added_late && line.session_id) {
    return (
      <button
        type="button"
        className="mt-3 min-h-[44px] w-full rounded-xl border border-rose-200 bg-rose-50 px-3 text-sm font-semibold text-rose-700"
        onClick={() => onRemove(line)}
      >
        Remove
      </button>
    )
  }
  if (pending) return null
  if (!line.session_id || line.line_kind === 'PAID_LEAVE' || line.line_kind === 'UNPAID_LEAVE') return null
  return (
    <button
      type="button"
      className="mt-3 min-h-[44px] w-full rounded-xl border border-indigo-200 bg-indigo-50 px-3 text-sm font-semibold text-indigo-700"
      onClick={() => onToggle?.(line)}
    >
      {excluded ? 'Include in this pay' : 'Leave out of this pay'}
    </button>
  )
}

function LineCard({ line, editable, pending, onToggle, onRemove }) {
  const excluded = line.included === false && !pending && line.breakdown_bucket !== 'in_pay'
  const amount = lineDisplayAmount(line)
  return (
    <li
      className={`rounded-xl border border-[#E2E8F0] bg-white p-3 shadow-sm ${excluded ? 'opacity-50' : ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold text-slate-900">{formatDisplayDate(line.session_date)}</p>
          {line.duration_minutes ? (
            <p className="text-xs text-slate-600">{line.duration_minutes} min</p>
          ) : null}
          <SessionLineTags line={line} />
        </div>
        <div className="shrink-0 text-right">
          <p className="text-base font-bold tabular-nums text-slate-900">{formatInr(amount)}</p>
          {pending ? (
            <p className="text-[10px] font-medium text-amber-800">Not in this month’s pay yet</p>
          ) : null}
        </div>
      </div>
      <SessionLineAction
        line={line}
        editable={editable}
        pending={pending}
        onToggle={onToggle}
        onRemove={onRemove}
      />
    </li>
  )
}

function LineList({ lines, editable, pending, onToggle, onRemove }) {
  if (!lines?.length) return null
  return (
    <ul className="space-y-2">
      {lines.map((line, idx) => (
        <LineCard
          key={lineKey(line, idx)}
          line={line}
          editable={editable}
          pending={pending}
          onToggle={onToggle}
          onRemove={onRemove}
        />
      ))}
    </ul>
  )
}

function AttendanceSummary({ data }) {
  const summary = data.attendance_summary
  const headerGist = formatTherapistHeaderSummary(data)
  const hasCalendarLeave =
    (summary?.paid_leaves ?? 0) > 0 || (summary?.unpaid_leaves ?? 0) > 0
  const leaveDeduction = data.leave_deduction_inr ?? 0

  return (
    <div className="space-y-2 rounded-xl border border-[#E2E8F0] bg-slate-50/80 p-4">
      {headerGist ? <p className="text-sm font-medium text-slate-700">{headerGist}</p> : null}
      {hasCalendarLeave ? (
        <p className="text-xs text-slate-600">
          Shadow leave: {summary.paid_leaves ?? 0} paid (no deduction)
          {(summary.unpaid_leaves ?? 0) > 0
            ? ` · ${summary.unpaid_leaves} unpaid (−${formatInr(leaveDeduction)})`
            : null}
        </p>
      ) : null}
      <div className="grid gap-3 pt-2 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Subtotal (in this pay)</p>
          <p className="text-lg font-bold text-slate-900">{formatInr(data.subtotal_inr)}</p>
        </div>
        {leaveDeduction > 0 ? (
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">Unpaid leave adjustment</p>
            <p className="text-lg font-bold text-rose-700">−{formatInr(leaveDeduction)}</p>
            <p className="text-[10px] text-slate-500">Shadow only — paid leave is not deducted.</p>
          </div>
        ) : null}
        {(data.pending_approval_count ?? data.pending_late_count ?? 0) > 0 ? (
          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase text-amber-700">Waiting on review</p>
            <p className="text-sm font-bold text-amber-900">
              {data.pending_approval_count ?? data.pending_late_count} item
              {(data.pending_approval_count ?? data.pending_late_count) === 1 ? '' : 's'} ·{' '}
              {formatInr(data.pending_approval_inr ?? data.pending_late_inr)} not in this pay yet
            </p>
          </div>
        ) : null}
        <div className="border-t border-[#E2E8F0] pt-3 sm:col-span-2">
          <p className="text-xs font-semibold uppercase text-indigo-600">Estimated pay</p>
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
        className="flex min-h-[44px] w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-800"
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
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

function CaseBreakdown({
  caseGroup,
  editable,
  month,
  onToggleSession,
  onRefresh,
  onRemoveLateSession,
  onNextMonthPlanChange,
}) {
  const homecare = isHomecareCaseGroup(caseGroup)
  const shadow = isShadowCaseGroup(caseGroup)
  const { inPay, pending, info } = partitionCaseLines(caseGroup)
  const displayIncluded = caseGroup.display_included_sessions ?? caseGroup.included_sessions ?? 0
  const attendanceStrip = caseGroup.has_activity !== false
    ? formatCaseAttendanceStrip(caseGroup.attendance, caseGroup.billing_profile)
    : null

  // Homecare: only actual sessions drive pay; absences/leave stay in info as cancelled.
  const inPayLines = homecare ? inPay.filter((l) => l.line_kind === 'SESSION' || !l.line_kind || l.line_kind === 'PENDING_LOG') : inPay
  // For homecare, move non-session "in_pay" child-away-still-paid into info if any leaked
  const infoLines = homecare
    ? [
        ...info,
        ...inPay.filter((l) => l.line_kind && l.line_kind !== 'SESSION'),
      ]
    : info

  return (
    <section className="overflow-hidden rounded-xl border border-[#E2E8F0] bg-white">
      <header className="border-b border-[#E2E8F0] bg-indigo-50/50 px-3 py-3 sm:px-4">
        <p className="font-semibold leading-snug text-slate-900">
          {caseGroup.case_code}
          {caseGroup.child_name ? ` · ${caseGroup.child_name}` : ''}
          <span className="ml-2 text-xs font-medium text-slate-500">
            {homecare ? 'Homecare' : shadow ? 'Shadow' : ''}
          </span>
        </p>
        <p className="mt-1 text-xs text-slate-600">
          {billingSummary(caseGroup.billing || caseGroup.billing_snapshot)}
        </p>
        {attendanceStrip ? (
          <p className="mt-1 text-xs font-medium text-slate-600">{attendanceStrip}</p>
        ) : null}
        <p className="mt-2 text-sm font-bold text-indigo-900">
          Case total: {formatInr(caseGroup.therapist_share_inr)}
          {displayIncluded ? (
            <span className="ml-2 font-normal text-slate-600">
              ({displayIncluded} session{displayIncluded === 1 ? '' : 's'} in payout
              {caseGroup.additional_sessions ? `, ${caseGroup.additional_sessions} extra` : ''})
            </span>
          ) : null}
        </p>
        {pending.length > 0 ? (
          <p className="mt-1 text-xs font-semibold text-amber-800">
            + {formatInr(caseGroup.pending_approval_inr ?? caseGroup.pending_late_inr)} waiting on review
          </p>
        ) : null}
      </header>

      <div className="space-y-4 px-3 py-3 sm:px-4">
        {inPayLines.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase text-emerald-800">In this pay</p>
            <LineList
              lines={inPayLines}
              editable={editable}
              onToggle={onToggleSession ? (line) => onToggleSession(caseGroup.case_id, line) : undefined}
            />
          </div>
        ) : (
          <p className="text-sm text-slate-500">No approved sessions in this pay yet.</p>
        )}

        {pending.length > 0 ? (
          <div className="border-t border-amber-100 pt-3">
            <p className="mb-2 text-xs font-semibold uppercase text-amber-800">Waiting on review</p>
            <LineList
              lines={pending}
              editable={editable}
              pending
              onRemove={
                onRemoveLateSession
                  ? (line) => line.flags?.added_late && line.session_id && onRemoveLateSession(line.session_id)
                  : undefined
              }
            />
          </div>
        ) : null}

        {infoLines.length > 0 ? (
          <details className="border-t border-slate-100 pt-3">
            <summary className="cursor-pointer text-xs font-semibold uppercase text-slate-600">
              Doesn’t change pay ({infoLines.length})
            </summary>
            <div className="mt-2">
              <LineList lines={infoLines} editable={false} />
            </div>
          </details>
        ) : null}

        {editable && month ? (
          <AddLateSessionForm caseId={caseGroup.case_id} month={month} onAdded={onRefresh} />
        ) : null}

        {showNextMonthSessionCount(caseGroup) && editable ? (
          <NextMonthSessionPlanEditor
            plan={caseGroup.next_month_session_plan}
            onChange={(plan) => onNextMonthPlanChange?.(caseGroup.case_id, plan)}
          />
        ) : null}

        {showNextMonthSessionCount(caseGroup) &&
        !editable &&
        nextMonthSessionCount(caseGroup.next_month_session_plan) > 0 ? (
          <div className="rounded-xl border border-sky-100 bg-sky-50/60 p-3">
            <p className="text-xs font-semibold uppercase text-sky-800">Next month sessions</p>
            <p className="mt-1 text-sm text-slate-800">
              {nextMonthSessionCount(caseGroup.next_month_session_plan)} session
              {nextMonthSessionCount(caseGroup.next_month_session_plan) === 1 ? '' : 's'} planned
              <span className="text-slate-500"> (not billed this month)</span>
            </p>
            {caseGroup.next_month_session_plan?.notes ? (
              <p className="mt-2 text-xs text-slate-600">{caseGroup.next_month_session_plan.notes}</p>
            ) : null}
          </div>
        ) : null}
      </div>
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
  onNextMonthPlanChange,
  hideSummary = false,
}) {
  const [summaryOpen, setSummaryOpen] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 640px)').matches : true,
  )

  if (!data) {
    return <p className="text-sm text-slate-500">No breakdown available.</p>
  }

  const leaveBalance = data.leave_balance
  const leaveCreditBanner = invoiceLeaveCreditBanner(leaveBalance)
  const rejectedNotes = data.rejected_notes || []
  const hasShadowCase = (data.cases || []).some(isShadowCaseGroup)

  return (
    <div className="space-y-6">
      {leaveCreditBanner && hasShadowCase ? (
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 text-sm text-slate-700">
          <p className="text-xs font-semibold uppercase text-indigo-700">Leave credits ({leaveBalance.year})</p>
          <p className="mt-1">
            Remaining: <strong>{leaveCreditBanner.remainingLabel}</strong>
          </p>
          <p className="mt-1 text-xs text-slate-600">{leaveCreditBanner.detail}</p>
          <p className="mt-1 text-xs text-slate-500">Credits reset each January. Unused credits do not carry forward.</p>
        </div>
      ) : null}

      {!hideSummary ? (
        <section>
          <button
            type="button"
            className="mb-2 flex min-h-[44px] w-full items-center justify-between text-left sm:hidden"
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

      {(data.cases || []).map((caseGroup) => (
        <CaseBreakdown
          key={caseGroup.case_id}
          caseGroup={caseGroup}
          editable={editable}
          month={month}
          onToggleSession={onToggleSession}
          onRefresh={onRefresh}
          onRemoveLateSession={onRemoveLateSession}
          onNextMonthPlanChange={onNextMonthPlanChange}
        />
      ))}

      <RejectedNotes notes={rejectedNotes} />
    </div>
  )
}
