import { StatusBadge } from './StatusBadge.jsx'

function ActionBtn({ children, variant = 'neutral', ...props }) {
  const styles = {
    neutral:
      'border-[#E2E8F0] bg-white text-slate-700 hover:bg-slate-50',
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

export function ReportCard({
  variant,
  report,
  onGenerateFromLogs,
  onStart,
  onContinue,
  onPreview,
  onSubmitReview,
  onView,
  onDownload,
}) {
  const isAttention = variant === 'attention'
  const isProgress = variant === 'progress'
  const isPublished = variant === 'published'

  const urgency =
    report.attentionType === 'overdue'
      ? 'border-red-200 bg-gradient-to-br from-red-50/95 to-white'
      : report.attentionType === 'rejected'
        ? 'border-rose-200 bg-gradient-to-br from-rose-50/95 to-white'
        : 'border-amber-200 bg-gradient-to-br from-amber-50/95 to-white'

  const baseCard =
    'rounded-2xl border border-[#E2E8F0] bg-white p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)] transition-transform duration-200 hover:scale-[1.01] hover:shadow-[0_12px_32px_rgba(15,23,42,0.08)]'

  return (
    <article className={`${baseCard} ${isAttention ? urgency : ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">{report.caseId}</p>
          <p className="mt-1 text-lg font-semibold text-slate-900">{report.child}</p>
          <p className="mt-0.5 text-sm font-medium text-slate-600">{report.month}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {isAttention && (
            <StatusBadge
              status={
                report.attentionType === 'overdue'
                  ? 'overdue'
                  : report.attentionType === 'rejected'
                    ? 'rejected'
                    : 'not_started'
              }
            />
          )}
          {isProgress && <StatusBadge status={report.status} />}
          {isPublished && <StatusBadge status="published" />}
        </div>
      </div>

      {(isAttention || isProgress) && report.dueInfo && (
        <p className="mt-3 text-sm font-semibold text-slate-700">{report.dueInfo}</p>
      )}
      {isProgress && report.lastUpdated && (
        <p className="mt-3 text-sm text-slate-500">
          Last updated <span className="font-medium text-slate-700">{report.lastUpdated}</span>
        </p>
      )}

      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        <button
          type="button"
          onClick={() => onGenerateFromLogs?.(report)}
          className="min-h-[40px] rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700"
        >
          Generate Draft from Logs
        </button>
      </div>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {isAttention && (
          <>
            {report.attentionType === 'not_started' && (
              <ActionBtn variant="primary" onClick={() => onStart?.(report)}>
                Start Report
              </ActionBtn>
            )}
            {(report.attentionType === 'overdue' || report.attentionType === 'rejected') && (
              <ActionBtn variant="accent" onClick={() => onContinue?.(report)}>
                Continue Editing
              </ActionBtn>
            )}
          </>
        )}
        {isProgress && (
          <>
            <ActionBtn variant="primary" onClick={() => onContinue?.(report)}>
              Continue Editing
            </ActionBtn>
            <ActionBtn variant="neutral" onClick={() => onPreview?.(report)}>
              Preview
            </ActionBtn>
            <ActionBtn variant="accent" onClick={() => onSubmitReview?.(report)}>
              Submit for Review
            </ActionBtn>
          </>
        )}
        {isPublished && (
          <>
            <ActionBtn variant="primary" onClick={() => onView?.(report)}>
              View
            </ActionBtn>
            <ActionBtn variant="neutral" onClick={() => onDownload?.(report)}>
              Download PDF
            </ActionBtn>
          </>
        )}
      </div>
    </article>
  )
}
