import { useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

export function ProgressReviewPanel({ reportId, canReview, onReturned }) {
  const [thread, setThread] = useState([])
  const [comment, setComment] = useState('')
  const [sectionComments, setSectionComments] = useState({ parent_summary: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!reportId) return
    apiFetch(`/api/v1/reports/${reportId}/progress/review-thread`)
      .then((data) => setThread(data.events || []))
      .catch(() => setThread([]))
  }, [reportId])

  async function handleReturn() {
    if (!comment.trim()) return
    setSaving(true)
    setError('')
    try {
      await apiFetch(`/api/v1/reports/${reportId}/return`, {
        method: 'POST',
        body: JSON.stringify({
          comment: comment.trim(),
          section_comments: Object.fromEntries(
            Object.entries(sectionComments).filter(([, v]) => v && v.trim())
          ),
        }),
      })
      setComment('')
      onReturned?.()
    } catch (err) {
      setError(err.message || 'Could not return report')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/30 clinical-shadow">
      <h3 className="text-lg font-bold text-lush-forest m-0 mb-3">CM review</h3>
      {error ? <p className="text-sm text-on-error-container bg-error-container px-3 py-2 rounded-lg">{error}</p> : null}
      {thread.length ? (
        <ul className="text-sm space-y-2 mb-4 max-h-48 overflow-y-auto">
          {thread.map((e) => (
            <li key={e.id} className="p-2 rounded-lg bg-surface-container">
              <span className="font-mono text-xs text-outline uppercase">{e.event_type}</span>
              {e.comment ? <p className="m-0 mt-1">{e.comment}</p> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-on-surface-variant mb-4">No review events yet.</p>
      )}
      {canReview ? (
        <div className="space-y-3">
          <label className="block text-xs font-bold uppercase text-outline" htmlFor="progress-return-note">
            Return note
          </label>
          <textarea
            id="progress-return-note"
            className="w-full border border-outline-variant rounded-xl p-3 text-sm min-h-[80px]"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <label className="block text-xs font-bold uppercase text-outline" htmlFor="progress-parent-comment">
            Parent summary comment (optional)
          </label>
          <textarea
            id="progress-parent-comment"
            className="w-full border border-outline-variant rounded-xl p-3 text-sm min-h-[60px]"
            value={sectionComments.parent_summary}
            onChange={(e) => setSectionComments((s) => ({ ...s, parent_summary: e.target.value }))}
          />
          <button
            type="button"
            className="px-4 py-2.5 rounded-xl border-2 border-amber-600 text-amber-800 font-bold min-h-[44px] disabled:opacity-50"
            disabled={saving || !comment.trim()}
            onClick={handleReturn}
          >
            {saving ? 'Returning…' : 'Return with comments'}
          </button>
        </div>
      ) : null}
    </section>
  )
}
