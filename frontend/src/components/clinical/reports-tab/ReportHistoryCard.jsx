import { reportTypeLabel } from '../../../lib/caseReportsCompose.js'
import { ReportStatusChip } from './ReportStatusChip.jsx'

const TYPE_ICONS = {
  observation_report: { icon: 'visibility', tone: 'green' },
  monthly_report: { icon: 'edit_note', tone: 'amber' },
  iep: { icon: 'psychology', tone: 'blue' },
  progress_report: { icon: 'task_alt', tone: 'teal' },
  cm_meeting_note: { icon: 'groups', tone: 'purple' },
}

function actionIcon(item) {
  const s = String(item.status || item.status_label || '').toLowerCase()
  if (s.includes('draft') || s.includes('return') || s.includes('change')) return 'edit'
  if (s.includes('approved') || s.includes('completed') || s.includes('active')) return 'visibility'
  return 'chevron_right'
}

function dateColumnLabel(item) {
  const s = String(item.status || item.status_label || '').toLowerCase()
  if (s.includes('draft')) return 'Last modified'
  if (s.includes('approved') || s.includes('completed')) return 'Logged date'
  if (item.type === 'iep') return 'Effective date'
  return 'Last updated'
}

export function ReportHistoryCard({ item, onAction }) {
  const meta = TYPE_ICONS[item.type] || { icon: 'description', tone: 'neutral' }
  const evidence = item.evidence || {}
  const icon = actionIcon(item)

  return (
    <article className="crt-history-card">
      <div className="crt-history-card__main">
        <div className={`crt-history-card__icon crt-history-card__icon--${meta.tone}`}>
          <span className="material-symbols-outlined" aria-hidden="true">{meta.icon}</span>
        </div>
        <div className="crt-history-card__copy">
          <h4 className="crt-history-card__title">{item.title || reportTypeLabel(item.type)}</h4>
          {item.summary ? <p className="crt-history-card__summary">{item.summary}</p> : null}
          {evidence.session_logs_used != null ? (
            <p className="crt-history-card__evidence">
              Session logs used: {evidence.session_logs_used}
              {evidence.session_logs_expected != null ? `/${evidence.session_logs_expected}` : ''}
              {evidence.missing_logs ? ` · Missing logs: ${evidence.missing_logs}` : ''}
            </p>
          ) : null}
        </div>
      </div>
      <div className="crt-history-card__aside">
        <ReportStatusChip status={item.status} statusLabel={item.status_label} />
        {item.last_updated ? (
          <div className="crt-history-card__date">
            <span className="crt-history-card__date-label">{dateColumnLabel(item)}</span>
            <span className="crt-history-card__date-value">{item.last_updated}</span>
          </div>
        ) : null}
        <button
          type="button"
          className="crt-history-card__action"
          aria-label={item.cta_label || 'Open report'}
          onClick={() => onAction?.(item)}
        >
          <span className="material-symbols-outlined" aria-hidden="true">{icon}</span>
        </button>
      </div>
    </article>
  )
}
