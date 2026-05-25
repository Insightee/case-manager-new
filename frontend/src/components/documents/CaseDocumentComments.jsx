import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { applyCommentToDetail } from '../../lib/caseDocumentCache.js'

export function CaseDocumentComments({
  documentId,
  detail,
  onDetailChange,
  canComment,
  commentPathPrefix = '/api/v1/documents',
}) {
  const [body, setBody] = useState('')
  const [commentType, setCommentType] = useState('GENERAL')
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const comments = detail?.comments ?? []

  async function loadComments() {
    const rows = await apiFetch(`${commentPathPrefix}/${documentId}/comments`)
    onDetailChange?.({ ...detail, comments: rows })
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!body.trim() || !canComment) return
    setActing(true)
    setError('')
    try {
      const row = await apiFetch(`${commentPathPrefix}/${documentId}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body: body.trim(), comment_type: commentType }),
      })
      const next = applyCommentToDetail({ ...detail, comments }, row)
      onDetailChange?.(next)
      setBody('')
      void loadComments()
    } catch (err) {
      setError(err.message || 'Could not add comment')
    } finally {
      setActing(false)
    }
  }

  return (
    <section className="case-docs-comments">
      <h3 style={{ fontSize: 15, margin: 0 }}>Comments</h3>
      {comments.length === 0 ? (
        <p style={{ fontSize: 13, color: '#9ca3af', margin: '8px 0 0' }}>No comments yet.</p>
      ) : (
        <ul>
          {comments.map((c) => (
            <li key={c.id}>
              <span style={{ fontSize: 12, color: '#6b7280' }}>
                {(c.comment_type || 'GENERAL').replace(/_/g, ' ')}
                {c.created_at ? ` · ${new Date(c.created_at).toLocaleString()}` : ''}
              </span>
              <p style={{ margin: '4px 0 0' }}>{c.body}</p>
            </li>
          ))}
        </ul>
      )}
      {canComment ? (
        <form onSubmit={handleSubmit} style={{ marginTop: 12 }}>
          <label style={{ display: 'block', fontSize: 13 }}>
            Type
            <select
              value={commentType}
              onChange={(e) => setCommentType(e.target.value)}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
            >
              <option value="GENERAL">General</option>
              <option value="GOAL_SUGGESTION">Goal suggestion</option>
              <option value="CHANGE_REQUEST">Change request</option>
            </select>
          </label>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={3}
            placeholder="Add a note for the care team"
            style={{ width: '100%', marginTop: 8, padding: 8 }}
          />
          {error ? (
            <p role="alert" style={{ color: '#b91c1c', fontSize: 13 }}>
              {error}
            </p>
          ) : null}
          <button type="submit" className="ic-btn ic-btn--primary" disabled={acting || !body.trim()} style={{ marginTop: 8 }}>
            Post comment
          </button>
        </form>
      ) : null}
    </section>
  )
}
