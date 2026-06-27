import { formatLogCommentCount } from '../../lib/sessionLogComments.js'

/** @param {{ count?: number | null, className?: string } & Record<string, unknown>} props */
export function LogCommentCountPill({ count, className = '' }) {
  const label = formatLogCommentCount(count)
  if (!label) return null
  return (
    <span className={`log-comment-count-pill${className ? ` ${className}` : ''}`}>
      {label}
    </span>
  )
}

/** @param {{ open_parent_comment_count?: number } | null | undefined} log */
export function LogOpenParentCommentBadge({ log }) {
  const count = log?.open_parent_comment_count
  if (!count || count <= 0) return null
  return (
    <span className="admin-badge admin-badge--warning sessions-dash__pill">
      {count} open parent {count === 1 ? 'comment' : 'comments'}
    </span>
  )
}
