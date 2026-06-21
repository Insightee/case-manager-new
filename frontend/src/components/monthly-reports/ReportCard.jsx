import { ClinicalStatusBadge } from '../clinical-ui/ClinicalStatusBadge.jsx'

function ActionBtn({ children, variant = 'neutral', ...props }) {
  const styles = {
    neutral: 'clinical-btn-secondary',
    primary: 'clinical-btn-primary',
    accent:  'clinical-btn-primary',
    danger:  'clinical-btn-secondary',
  }
  return (
    <button
      type="button"
      className={`${styles[variant]}`}
      style={{ fontSize: '0.8125rem', minHeight: '40px', padding: '0.4rem 0.875rem' }}
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
  const isProgress  = variant === 'progress'
  const isPublished = variant === 'published'

  const urgencyExtra =
    report.attentionType === 'overdue'  ? 'clinical-case-queue-card--overdue'
    : report.attentionType === 'rejected' ? 'clinical-case-queue-card--rejected'
    : ''

  return (
    <article className={`clinical-case-queue-card ${urgencyExtra}`}
      style={
        isAttention && report.attentionType
          ? {
              borderLeftColor:
                report.attentionType === 'overdue' ? 'var(--clinical-red)'
                : report.attentionType === 'rejected' ? '#f43f5e'
                : 'var(--clinical-amber)',
              borderLeftWidth: 3,
              background:
                report.attentionType === 'overdue' ? 'var(--clinical-red-soft)'
                : report.attentionType === 'rejected' ? '#fff1f2'
                : 'var(--clinical-amber-soft)',
            }
          : undefined
      }
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div>
          <p style={{ fontSize: '0.6875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--clinical-purple)', margin: '0 0 0.2rem' }}>
            {report.caseId}
          </p>
          <p className="clinical-case-queue-card__name">{report.child}</p>
          <p style={{ fontSize: '0.8125rem', color: 'var(--clinical-muted)', margin: 0 }}>{report.month}</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.375rem' }}>
          {isAttention && (
            <ClinicalStatusBadge
              status={
                report.attentionType === 'overdue'  ? 'REJECTED'
                : report.attentionType === 'rejected' ? 'REJECTED'
                : 'DRAFT'
              }
              customLabel={
                report.attentionType === 'overdue' ? 'Overdue'
                : report.attentionType === 'rejected' ? 'Revision Needed'
                : 'Not Started'
              }
            />
          )}
          {isProgress  && <ClinicalStatusBadge status={report.status} />}
          {isPublished && <ClinicalStatusBadge status="PUBLISHED" />}
        </div>
      </div>

      {(isAttention || isProgress) && report.dueInfo ? (
        <p style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#334155', margin: '0.5rem 0 0' }}>{report.dueInfo}</p>
      ) : null}
      {isProgress && report.lastUpdated ? (
        <p style={{ fontSize: '0.8125rem', color: 'var(--clinical-muted)', margin: '0.25rem 0 0' }}>
          Last updated <strong>{report.lastUpdated}</strong>
        </p>
      ) : null}

      <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
        <button
          type="button"
          onClick={() => onGenerateFromLogs?.(report)}
          className="clinical-btn-primary"
          style={{ fontSize: '0.8125rem', minHeight: '40px', padding: '0.4rem 0.875rem' }}
        >
          Generate Draft from Logs
        </button>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem', marginTop: '0.375rem' }}>
        {isAttention && (
          <>
            {report.attentionType === 'not_started' && (
              <ActionBtn variant="primary" onClick={() => onStart?.(report)}>Start Report</ActionBtn>
            )}
            {(report.attentionType === 'overdue' || report.attentionType === 'rejected') && (
              <ActionBtn variant="accent" onClick={() => onContinue?.(report)}>Continue Editing</ActionBtn>
            )}
          </>
        )}
        {isProgress && (
          <>
            <ActionBtn variant="primary" onClick={() => onContinue?.(report)}>Continue Editing</ActionBtn>
            <ActionBtn variant="neutral" onClick={() => onPreview?.(report)}>Preview</ActionBtn>
            {onSubmitReview ? (
              <ActionBtn variant="accent" onClick={() => onSubmitReview?.(report)}>Submit for Review</ActionBtn>
            ) : null}
          </>
        )}
        {isPublished && (
          <>
            <ActionBtn variant="primary" onClick={() => onView?.(report)}>View</ActionBtn>
            {onDownload ? (
              <ActionBtn variant="neutral" onClick={() => onDownload?.(report)}>Download PDF</ActionBtn>
            ) : null}
          </>
        )}
      </div>
    </article>
  )
}
