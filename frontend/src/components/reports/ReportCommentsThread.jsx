import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

/**
 * @param {{
 *   commentsPath: string,
 *   postPath?: string,
 *   canPost?: boolean,
 *   title?: string,
 *   initialComments?: Array<{ id: number, body: string, author_name?: string, created_at?: string, comment_type?: string }>,
 *   refreshToken?: string | number,
 * }} props
 */
export function ReportCommentsThread({
  commentsPath,
  postPath,
  canPost = false,
  title = 'Comments',
  initialComments,
  refreshToken,
}) {
  const [comments, setComments] = useState(initialComments || [])
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    if (!commentsPath) return
    setLoading(true)
    setErr('')
    try {
      const rows = await apiFetch(commentsPath)
      setComments(Array.isArray(rows) ? rows : rows?.comments || [])
    } catch (e) {
      setErr(e.message || 'Could not load comments')
    } finally {
      setLoading(false)
    }
  }, [commentsPath])

  useEffect(() => {
    if (initialComments) {
      setComments(initialComments)
    }
  }, [initialComments, refreshToken])

  useEffect(() => {
    load()
  }, [load, refreshToken])

  async function submit(e) {
    e.preventDefault()
    if (!postPath || !body.trim()) return
    setSaving(true)
    setErr('')
    try {
      await apiFetch(postPath, {
        method: 'POST',
        body: JSON.stringify({ body: body.trim(), comment_type: 'GENERAL' }),
      })
      setBody('')
      await load()
    } catch (ex) {
      setErr(ex.message || 'Could not post comment')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="admin-reports__comments-thread">
      {title ? <h3>{title}</h3> : null}
      {loading && comments.length === 0 ? <p className="admin-muted">Loading comments…</p> : null}
      {err ? <p className="admin-alert admin-alert--error">{err}</p> : null}
      <ul className="admin-reports__comments-list" aria-live="polite">
        {comments.map((c) => (
          <li key={c.id} className="admin-reports__comments-item">
            <span className="admin-reports__comments-meta">
              {c.author_name || 'User'}
              {c.created_at ? ` · ${new Date(c.created_at).toLocaleString()}` : ''}
              {c.comment_type && c.comment_type !== 'GENERAL' ? ` · ${c.comment_type}` : ''}
            </span>
            <p className="admin-reports__comments-body">{c.body}</p>
          </li>
        ))}
        {!loading && comments.length === 0 ? (
          <li className="admin-reports__comments-empty">No comments yet — post below to start the thread.</li>
        ) : null}
      </ul>
      {canPost && postPath ? (
        <form onSubmit={submit} className="admin-reports__comments-form">
          <label className="admin-reports__comments-form-label" htmlFor="report-discussion-body">
            Add to discussion
          </label>
          <textarea
            id="report-discussion-body"
            className="admin-input"
            rows={3}
            placeholder="Visible to reviewers on this report…"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <button type="submit" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={saving || !body.trim()}>
            {saving ? 'Posting…' : 'Post comment'}
          </button>
        </form>
      ) : null}
    </section>
  )
}
