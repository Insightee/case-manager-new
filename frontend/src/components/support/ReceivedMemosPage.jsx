import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { MemoThreadDrawer } from './MemoThreadDrawer.jsx'

const STATUS_COLORS = {
  OPEN: { bg: '#eef2ff', color: '#4f46e5', label: 'Open' },
  PENDING_REPLY: { bg: '#fffbeb', color: '#d97706', label: 'Pending Reply' },
  UNDER_REVIEW: { bg: '#f0fdf4', color: '#16a34a', label: 'Under Review' },
  CLOSED: { bg: '#f3f4f6', color: '#4b5563', label: 'Closed' },
}

/** Inbox for staff who receive compliance / HR memos (CM, supervisor, therapist, …). */
export function ReceivedMemosPage({ embedded = false }) {
  const [memos, setMemos] = useState([])
  const [stats, setStats] = useState({
    open: 0,
    pending_reply: 0,
    under_review: 0,
    closed_this_month: 0,
    awaiting_response: 0,
  })
  const [loading, setLoading] = useState(true)
  const [selectedMemoId, setSelectedMemoId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [replyText, setReplyText] = useState('')
  const [replyFiles, setReplyFiles] = useState([])
  const [replyBusy, setReplyBusy] = useState(false)
  const [replyError, setReplyError] = useState('')

  async function loadData() {
    setLoading(true)
    try {
      const [list, metrics] = await Promise.all([apiFetch('/api/v1/memos'), apiFetch('/api/v1/memos/stats')])
      setMemos(list || [])
      setStats(
        metrics || { open: 0, pending_reply: 0, under_review: 0, closed_this_month: 0, awaiting_response: 0 },
      )
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  async function loadMemoDetail(id) {
    setDetailLoading(true)
    setDetail(null)
    setReplyText('')
    setReplyFiles([])
    setReplyError('')
    try {
      setDetail(await apiFetch(`/api/v1/memos/${id}`))
    } catch (err) {
      console.error(err)
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    if (selectedMemoId) loadMemoDetail(selectedMemoId)
    else setDetail(null)
  }, [selectedMemoId])

  async function acknowledgeMemo() {
    try {
      await apiFetch(`/api/v1/memos/${selectedMemoId}/acknowledge`, { method: 'POST' })
      await loadMemoDetail(selectedMemoId)
      loadData()
    } catch (err) {
      alert(err.message || 'Could not acknowledge memo')
    }
  }

  async function submitReply(e) {
    e.preventDefault()
    if (!replyText.trim()) return
    setReplyBusy(true)
    setReplyError('')
    try {
      const formData = new FormData()
      formData.append('body', replyText)
      replyFiles.forEach((file) => formData.append('files', file))
      await apiFetch(`/api/v1/memos/${selectedMemoId}/messages`, { method: 'POST', body: formData })
      setReplyText('')
      setReplyFiles([])
      await loadMemoDetail(selectedMemoId)
      loadData()
    } catch (err) {
      setReplyError(err.message || 'Could not send message')
    } finally {
      setReplyBusy(false)
    }
  }

  const rootPadding = embedded ? '0' : '1.25rem'

  return (
    <div style={{ padding: rootPadding, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {stats.awaiting_response > 0 ? (
        <div
          style={{
            background: '#fffbeb',
            border: '1px solid #fef3c7',
            borderRadius: 10,
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <span style={{ fontSize: '1.25rem' }} aria-hidden>
            ⚠️
          </span>
          <div>
            <p style={{ fontWeight: 700, color: '#b45309', margin: 0, fontSize: '0.9rem' }}>Pending action required</p>
            <p style={{ fontSize: '0.8rem', color: '#d97706', margin: '2px 0 0 0' }}>
              You have <strong>{stats.awaiting_response}</strong> memo{stats.awaiting_response !== 1 ? 's' : ''} awaiting
              your response or acknowledgement.
            </p>
          </div>
        </div>
      ) : null}

      <div>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', margin: '0 0 12px 0' }}>Memos received</h3>
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>Loading received memos…</div>
        ) : memos.length === 0 ? (
          <div
            style={{
              padding: '3rem',
              textAlign: 'center',
              background: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: 12,
              color: '#64748b',
            }}
          >
            <p style={{ fontWeight: 600, margin: 0 }}>No memos received</p>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: 4 }}>
              You have no compliance or administrative memos assigned to you.
            </p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1rem' }}>
            {memos.map((m) => {
              const badge = STATUS_COLORS[m.status] || { bg: '#f1f5f9', color: '#475569', label: m.status }
              const isActionRequired =
                m.status !== 'CLOSED' && (m.reply_required || m.acknowledgement_only) && !m.acknowledged
              return (
                <div
                  key={m.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedMemoId(m.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedMemoId(m.id)
                    }
                  }}
                  style={{
                    background: '#fff',
                    border: isActionRequired ? '2px solid #f59e0b' : '1px solid #e2e8f0',
                    borderRadius: 12,
                    padding: '1.25rem',
                    cursor: 'pointer',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                    position: 'relative',
                  }}
                >
                  {!m.viewed ? (
                    <span
                      aria-label="Unread"
                      style={{
                        position: 'absolute',
                        top: 12,
                        right: 12,
                        width: 8,
                        height: 8,
                        background: '#ef4444',
                        borderRadius: '50%',
                      }}
                    />
                  ) : null}
                  <div style={{ display: 'flex', gap: 6, marginBottom: 8, alignItems: 'center' }}>
                    <span style={{ fontSize: '0.675rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>
                      {m.memo_code}
                    </span>
                    <span style={{ margin: '0 4px', color: '#cbd5e1' }}>|</span>
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: 4,
                        background: badge.bg,
                        color: badge.color,
                      }}
                    >
                      {badge.label}
                    </span>
                  </div>
                  <h4 style={{ margin: '0 0 6px 0', fontSize: '0.975rem', fontWeight: 700, color: '#1e293b' }}>{m.subject}</h4>
                  <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '0 0 10px 0' }}>
                    From: {m.sender_name || 'Operations'} · Issued: {new Date(m.created_at).toLocaleDateString()}
                  </p>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderTop: '1px solid #f1f5f9',
                      paddingTop: 8,
                      marginTop: 10,
                    }}
                  >
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      Category: <strong>{m.category}</strong>
                    </span>
                    {m.due_date ? (
                      <span
                        style={{
                          fontSize: '0.75rem',
                          color: isActionRequired ? '#b45309' : '#64748b',
                          fontWeight: isActionRequired ? 600 : 400,
                        }}
                      >
                        Due: {new Date(m.due_date).toLocaleDateString()}
                      </span>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <MemoThreadDrawer
        open={Boolean(selectedMemoId)}
        onClose={() => setSelectedMemoId(null)}
        memoCode={detail?.memo_code}
        title="Memo details"
        loading={detailLoading || !detail}
        loadingLabel="Loading memo details…"
        timelineLabel="Timeline & messages"
        memoSection={
          detail ? (
            <>
              <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: 600, padding: '2px 6px', borderRadius: 4, background: '#f1f5f9', color: '#475569' }}>
                  {detail.category}
                </span>
                <span style={{ fontSize: '0.7rem', fontWeight: 600, padding: '2px 6px', borderRadius: 4, background: '#fee2e2', color: '#ef4444' }}>
                  {detail.priority}
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: STATUS_COLORS[detail.status]?.bg || '#f1f5f9',
                    color: STATUS_COLORS[detail.status]?.color || '#475569',
                  }}
                >
                  {STATUS_COLORS[detail.status]?.label || detail.status}
                </span>
              </div>
              <h5 style={{ margin: '0 0 8px 0', fontSize: '1.1rem', fontWeight: 700, color: '#1e293b' }}>{detail.subject}</h5>
              <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: 12 }}>
                From: {detail.sender?.full_name || 'Operations'} · Issued: {new Date(detail.created_at).toLocaleDateString()}
              </p>
              <p
                style={{
                  fontSize: '0.875rem',
                  color: '#334155',
                  whiteSpace: 'pre-wrap',
                  lineHeight: 1.5,
                  background: '#fff',
                  padding: 12,
                  borderRadius: 8,
                  border: '1px solid #e2e8f0',
                  margin: 0,
                }}
              >
                {detail.details}
              </p>
              {detail.attachments?.length > 0 ? (
                <div style={{ marginTop: 12 }}>
                  <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569', margin: '0 0 6px 0' }}>Attachments</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {detail.attachments.map((a) => (
                      <a
                        key={a.id}
                        href={`/api/v1/memos/${detail.id}/attachments/${a.id}`}
                        download
                        style={{
                          fontSize: '0.8rem',
                          color: '#4f46e5',
                          textDecoration: 'none',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        📎 {a.file_name}{' '}
                        <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>({(a.size_bytes / 1024).toFixed(1)} KB)</span>
                      </a>
                    ))}
                  </div>
                </div>
              ) : null}
              {detail.acknowledgement_only && !detail.acknowledged_at ? (
                <div
                  style={{
                    marginTop: 16,
                    background: '#fffbeb',
                    border: '1px solid #fef3c7',
                    padding: 12,
                    borderRadius: 8,
                    textAlign: 'center',
                  }}
                >
                  <p style={{ fontSize: '0.8rem', color: '#b45309', margin: '0 0 8px 0', fontWeight: 500 }}>
                    Please read and acknowledge this memo:
                  </p>
                  <button
                    type="button"
                    onClick={acknowledgeMemo}
                    style={{
                      background: '#d97706',
                      color: '#fff',
                      border: 'none',
                      padding: '6px 16px',
                      borderRadius: 6,
                      fontWeight: 700,
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                    }}
                  >
                    I acknowledge this memo
                  </button>
                </div>
              ) : null}
              {detail.acknowledged_at ? (
                <div style={{ marginTop: 12, fontSize: '0.8rem', color: '#16a34a', fontWeight: 600 }}>
                  ✓ Acknowledged on {new Date(detail.acknowledged_at).toLocaleDateString()}
                </div>
              ) : null}
            </>
          ) : null
        }
        timelineSection={
          detail?.messages?.map((msg) => (
            <div
              key={msg.id}
              style={{
                alignSelf: msg.author?.id === detail.recipient?.id ? 'flex-end' : 'flex-start',
                background: msg.author?.id === detail.recipient?.id ? '#eef2ff' : '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: 12,
                padding: '10px 12px',
                maxWidth: '85%',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 4 }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#1e293b' }}>{msg.author?.full_name}</span>
                <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>{new Date(msg.created_at).toLocaleDateString()}</span>
              </div>
              <p style={{ fontSize: '0.85rem', color: '#334155', margin: 0, whiteSpace: 'pre-wrap' }}>{msg.body}</p>
              {msg.attachments?.map((a) => (
                <div key={a.id} style={{ marginTop: 6, borderTop: '1px solid #f1f5f9', paddingTop: 4 }}>
                  <a
                    href={`/api/v1/memos/${detail.id}/attachments/${a.id}`}
                    download
                    style={{ fontSize: '0.75rem', color: '#4f46e5', textDecoration: 'none' }}
                  >
                    📎 {a.file_name}
                  </a>
                </div>
              ))}
            </div>
          )) ?? null
        }
        footer={
          detail?.reply_required && detail.status !== 'CLOSED' ? (
            <form onSubmit={submitReply} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {replyError ? <div style={{ fontSize: '0.75rem', color: '#ef4444' }}>{replyError}</div> : null}
              <textarea
                rows={2}
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Your response…"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  border: '1px solid #cbd5e1',
                  borderRadius: 8,
                  boxSizing: 'border-box',
                  fontFamily: 'inherit',
                  resize: 'none',
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <input
                  type="file"
                  multiple
                  onChange={(e) => setReplyFiles(Array.from(e.target.files || []))}
                  style={{ fontSize: '0.75rem', maxWidth: 180 }}
                />
                <button
                  type="submit"
                  disabled={replyBusy}
                  style={{
                    background: '#6366f1',
                    color: '#fff',
                    border: 'none',
                    padding: '6px 14px',
                    borderRadius: 6,
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    opacity: replyBusy ? 0.7 : 1,
                  }}
                >
                  Submit reply
                </button>
              </div>
            </form>
          ) : null
        }
      />
    </div>
  )
}
