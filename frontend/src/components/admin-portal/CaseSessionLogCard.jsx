import { Link } from 'react-router-dom'
import { SessionLogReadOnly } from '../daily-logs/SessionLogReadOnly.jsx'
import { RejectWithComment, StatusBadge } from './ui/index.js'
import { LogCommentCountPill, LogOpenParentCommentBadge } from '../shared/LogCommentCountBadge.jsx'
import {
  caseSessionLogCardTone,
  formatCaseSessionLogCardMeta,
  formatCaseSessionLogCardTitle,
} from '../../lib/caseSessionLogDisplay.js'
import { sessionHasTimeEdit } from '../../lib/sessionTimes.js'
import { TransitionLogBadge } from '../daily-logs/TransitionLogBadge.jsx'

function SessionLogBadges({ session, log }) {
  return (
    <>
      {session ? <StatusBadge status={session.status} /> : null}
      {log ? <StatusBadge status={log.approval_status} /> : null}
      <TransitionLogBadge log={log} />
      {log?.comment_count > 0 ? <LogCommentCountPill count={log.comment_count} /> : null}
      {log?.resubmitted_at ? (
        <span className="admin-badge admin-badge--info sessions-dash__pill">Resubmitted</span>
      ) : null}
      <LogOpenParentCommentBadge log={log} />
      {sessionHasTimeEdit(session, log) ? (
        <span className="admin-badge admin-badge--warning sessions-dash__pill">Times edited</span>
      ) : null}
      {session?.duplicate_day_session || log?.duplicate_day_session ? (
        <span className="admin-badge admin-badge--warning sessions-dash__pill">Same-day duplicate</span>
      ) : null}
    </>
  )
}

function SessionLogExpandableContent({
  expandKey,
  log,
  session,
  caseId,
  expanded,
  onToggleExpand,
  canReview,
  onReviewLog,
  actingLogId,
  rejectingLogId,
  setRejectingLogId,
  rejectComment,
  setRejectComment,
  analyticsSessionId,
  onCommentCountChange,
}) {
  if (!log) return null

  const hasTimeEdit = sessionHasTimeEdit(session, log)
  const analyticsHref = analyticsSessionId
    ? `/admin/logs?tab=sessions&case_id=${caseId}&session_id=${analyticsSessionId}`
    : `/admin/logs?tab=sessions&case_id=${caseId}`

  return (
    <>
      {expanded ? (
        <div className="case-session-log-card__body">
          <SessionLogReadOnly
            log={log}
            session={session}
            variant="admin"
            hideHeader
            hideTimesSummary
            onCommentCountChange={onCommentCountChange}
          />
          {log.approval_status === 'PENDING' && canReview ? (
            <div className="case-session-log-card__review">
              <RejectWithComment
                rejecting={rejectingLogId === log.id}
                comment={rejectingLogId === log.id ? rejectComment : ''}
                onCommentChange={setRejectComment}
                onStartReject={() => {
                  setRejectingLogId(log.id)
                  setRejectComment('')
                }}
                onCancelReject={() => {
                  setRejectingLogId(null)
                  setRejectComment('')
                }}
                onConfirmReject={() => {
                  const note = rejectComment.trim()
                  if (!note) return
                  onReviewLog(log.id, 'reject', note)
                  setRejectingLogId(null)
                  setRejectComment('')
                }}
                onApprove={() => onReviewLog(log.id, 'approve')}
                processing={actingLogId === log.id}
                approveLabel={hasTimeEdit ? 'Approve log & times' : 'Approve'}
                placeholder="Why is this log rejected? (required)"
              />
            </div>
          ) : null}
        </div>
      ) : null}
      <footer className="case-session-log-card__footer">
        <button
          type="button"
          className="case-session-log-card__toggle"
          onClick={() => onToggleExpand(expandKey)}
          aria-expanded={expanded}
        >
          {expanded ? 'Hide full log' : 'View full log'}
        </button>
        <Link to={analyticsHref} className="case-session-log-card__analytics-link">
          Sessions analytics
        </Link>
      </footer>
    </>
  )
}

export function CaseSessionLogCard({
  session,
  log,
  caseId,
  expandKey,
  expanded,
  highlight = false,
  highlightRef,
  canReview,
  onToggleExpand,
  onReviewLog,
  actingLogId,
  rejectingLogId,
  setRejectingLogId,
  rejectComment,
  setRejectComment,
  onCommentCountChange,
}) {
  const title = formatCaseSessionLogCardTitle(session, log)
  const meta = formatCaseSessionLogCardMeta(session, log)
  const tone = caseSessionLogCardTone(session, log)
  const cardClass = [
    'case-session-log-card',
    highlight ? 'case-session-log-card--highlight' : '',
    tone !== 'default' ? `case-session-log-card--${tone}` : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <article ref={highlightRef} className={cardClass}>
      <header className="case-session-log-card__head">
        <div className="case-session-log-card__copy">
          <h3 className="case-session-log-card__title">{title}</h3>
          {meta ? <p className="case-session-log-card__meta">{meta}</p> : null}
        </div>
        <div className="case-session-log-card__badges">
          <SessionLogBadges session={session} log={log} />
        </div>
      </header>

      {!log ? (
        <p className="case-session-log-card__pending">
          {session?.status === 'IN_PROGRESS' || session?.status === 'SCHEDULED'
            ? 'Session in progress — log not submitted yet.'
            : 'No therapist log submitted for this session.'}
        </p>
      ) : (
        <SessionLogExpandableContent
          expandKey={expandKey}
          log={log}
          session={session}
          caseId={caseId}
          expanded={expanded}
          onToggleExpand={onToggleExpand}
          canReview={canReview}
          onReviewLog={onReviewLog}
          actingLogId={actingLogId}
          rejectingLogId={rejectingLogId}
          setRejectingLogId={setRejectingLogId}
          rejectComment={rejectComment}
          setRejectComment={setRejectComment}
          analyticsSessionId={session?.id ?? log?.session_id}
          onCommentCountChange={onCommentCountChange}
        />
      )}
    </article>
  )
}
