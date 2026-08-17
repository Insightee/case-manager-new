/** @param {number | undefined | null} count */
export function formatLogCommentCount(count) {
  if (!count || count <= 0) return null
  return count === 1 ? '1 comment' : `${count} comments`
}

/** @param {{ comment_count?: number } | null | undefined} log */
export function logCommentMetaSuffix(log) {
  const label = formatLogCommentCount(log?.comment_count)
  return label ? ` · ${label}` : ''
}

/** @param {{ id?: number, therapist_user_id?: number, therapist_name?: string } | null | undefined} session @param {{ comment_count?: number, therapist_name?: string, therapist_user_id?: number } | null | undefined} log */
export function buildSessionLogMeta(session, log) {
  if (!session) return ''
  let meta = `Session #${session.id}`
  const therapistName = session.therapist_name || log?.therapist_name
  if (therapistName) {
    meta += ` · ${therapistName}`
  } else {
    const therapistId = session.therapist_user_id ?? log?.therapist_user_id
    if (therapistId) meta += ` · Therapist #${therapistId}`
  }
  return meta + logCommentMetaSuffix(log)
}

/** @param {Record<string, { comment_count?: number, open_parent_comment_count?: number }>} countsById */
function mergeCommentCountsIntoLogs(logs, countsById) {
  if (!countsById || typeof countsById !== 'object') return logs
  return logs.map((log) => {
    const row = countsById[String(log.id)] ?? countsById[log.id]
    if (!row) return log
    return {
      ...log,
      comment_count: row.comment_count ?? log.comment_count ?? 0,
      open_parent_comment_count: row.open_parent_comment_count ?? log.open_parent_comment_count ?? 0,
    }
  })
}

/** @param {number[]} logIds @param {(path: string, options?: object) => Promise<unknown>} apiFetch */
async function fetchCommentCountsViaCommentsEndpoint(logIds, apiFetch) {
  const map = {}
  const chunkSize = 8
  for (let i = 0; i < logIds.length; i += chunkSize) {
    const slice = logIds.slice(i, i + chunkSize)
    await Promise.all(
      slice.map(async (id) => {
        try {
          const comments = await apiFetch(`/api/v1/daily-logs/${id}/comments`)
          const rows = Array.isArray(comments) ? comments : []
          map[id] = {
            comment_count: rows.length,
            open_parent_comment_count: rows.filter(
              (c) => c.author_role === 'parent' && c.status === 'open' && c.visibility === 'parent_team',
            ).length,
          }
        } catch {
          map[id] = { comment_count: 0, open_parent_comment_count: 0 }
        }
      }),
    )
  }
  return map
}

/** @param {Array<{ id?: number, comment_count?: number, open_parent_comment_count?: number }>} logs */
export async function enrichLogsWithCommentCounts(logs, apiFetch) {
  if (!Array.isArray(logs) || logs.length === 0) return logs
  const ids = [...new Set(logs.map((l) => l?.id).filter((id) => id != null))]
  if (ids.length === 0) return logs

  let countsById = null
  try {
    const batch = await apiFetch(`/api/v1/daily-logs/comment-counts?log_ids=${ids.join(',')}`)
    if (batch && typeof batch === 'object') {
      countsById = batch
    }
  } catch {
    countsById = null
  }

  if (countsById && Object.keys(countsById).length > 0) {
    return mergeCommentCountsIntoLogs(logs, countsById)
  }

  const fallback = await fetchCommentCountsViaCommentsEndpoint(ids, apiFetch)
  return mergeCommentCountsIntoLogs(logs, fallback)
}
