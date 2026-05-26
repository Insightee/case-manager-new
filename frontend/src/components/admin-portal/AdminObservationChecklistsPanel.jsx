import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPanel } from './ui/index.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'

export function AdminObservationChecklistsPanel() {
  const { canReviewReports } = useModuleWrite()
  const [items, setItems] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await apiFetch('/api/v1/admin/observation-checklists'))
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (id) => {
    setSelectedId(id)
    setError('')
    try {
      setDetail(await apiFetch(`/api/v1/admin/observation-checklists/${id}`))
    } catch (err) {
      setDetail(null)
      setError(err.message || 'Could not load checklist')
    }
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  async function approve() {
    if (!selectedId) return
    setActing(true)
    setError('')
    try {
      await apiFetch(`/api/v1/admin/observation-checklists/${selectedId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ comment: comment.trim() || null, share_with_parent: true }),
      })
      setComment('')
      setDetail(null)
      setSelectedId(null)
      await loadList()
    } catch (err) {
      setError(err.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  async function reject() {
    if (!selectedId || !comment.trim()) {
      setError('Add a comment explaining what to change.')
      return
    }
    setActing(true)
    setError('')
    try {
      await apiFetch(`/api/v1/admin/observation-checklists/${selectedId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ comment: comment.trim() }),
      })
      setComment('')
      setDetail(null)
      setSelectedId(null)
      await loadList()
    } catch (err) {
      setError(err.message || 'Reject failed')
    } finally {
      setActing(false)
    }
  }

  return (
    <AdminPanel title="Observation checklists awaiting review">
      {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
      {!loading && items.length === 0 ? (
        <p className="text-sm text-slate-500">No checklists pending review.</p>
      ) : (
        <ul className="log-list" style={{ marginBottom: 16 }}>
          {items.map((row) => (
            <li key={row.id}>
              <button type="button" onClick={() => loadDetail(row.id)} style={{ width: '100%', textAlign: 'left' }}>
                <strong>
                  {row.case_code} · {row.child_name}
                </strong>
                <span style={{ display: 'block', fontSize: 13, color: '#64748b' }}>
                  {row.therapist_name} · submitted{' '}
                  {row.submitted_at ? new Date(row.submitted_at).toLocaleString() : '—'}
                  {row.is_overdue ? ' · overdue' : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {error ? (
        <p role="alert" style={{ color: '#b91c1c' }}>
          {error}
        </p>
      ) : null}

      {detail ? (
        <div className="card" style={{ padding: 16 }}>
          <p style={{ margin: '0 0 8px' }}>
            <Link to={`/admin/cases/${detail.case_id}`}>Open case {detail.case_id}</Link>
          </p>
          {(detail.sections || []).map((section) => (
            <div key={section.key} style={{ marginBottom: 12 }}>
              <p style={{ margin: '0 0 4px', fontWeight: 600, fontSize: '0.85rem' }}>{section.label}</p>
              <p style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                {detail.responses?.[section.key] || '—'}
              </p>
            </div>
          ))}
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            placeholder="Optional note on approve; required on reject"
            style={{ width: '100%', marginTop: 8, padding: 8 }}
          />
          {canReviewReports(detail.product_module || 'homecare') ? (
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button type="button" className="admin-btn admin-btn--primary" disabled={acting} onClick={approve}>
              Approve & share report
            </button>
            <button type="button" className="admin-btn admin-btn--secondary" disabled={acting} onClick={reject}>
              Request changes
            </button>
          </div>
          ) : (
            <p className="admin-muted" style={{ marginTop: 12, fontSize: '0.8rem' }}>
              View-only for this programme — cannot approve checklists.
            </p>
          )}
        </div>
      ) : null}
    </AdminPanel>
  )
}
