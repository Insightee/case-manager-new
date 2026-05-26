import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

/**
 * @param {{ commentsPath: string, postPath?: string, canPost?: boolean, title?: string }} props
 */
export function ReportCommentsThread({ commentsPath, postPath, canPost = false, title = 'Comments' }) {
  const [comments, setComments] = useState([])
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
      setComments([])
    } finally {
      setLoading(false)
    }
  }, [commentsPath])

  useEffect(() => {
    load()
  }, [load])

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
      <h3>{title}</h3>
      {loading ? <p className="admin-muted">Loading comments…</p> : null}
      {err ? <p className="admin-alert admin-alert--error">{err}</p> : null}
      <ul className="admin-reports__comments-list">
        {comments.map((c) => (
          <li key={c.id} className="admin-reports__comments-item">
            <span className="admin-reports__comments-meta">
              {c.author_name || 'User'}
              {c.created_at ? ` · ${new Date(c.created_at).toLocaleString()}` : ''}
            </span>
            <p>{c.body}</p>
          </li>
        ))}
        {!loading && comments.length === 0 ? (
          <li className="admin-muted">No comments yet.</li>
        ) : null}
      </ul>
      {canPost && postPath ? (
        <form onSubmit={submit} className="admin-reports__comments-form">
          <textarea
            className="admin-input"
            rows={2}
            placeholder="Add a comment…"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <button type="submit" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={saving}>
            Post comment
          </button>
        </form>
      ) : null}
    </section>
  )
}
