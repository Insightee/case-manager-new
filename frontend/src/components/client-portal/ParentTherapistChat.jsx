import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatTimeIN12 } from '../../lib/datetime.js'
import { replyParentTicket } from '../../lib/ticketFormUtils.js'
import { TicketAttachmentList } from '../support/TicketAttachmentList.jsx'
import { TicketFileInput } from '../support/TicketFileInput.jsx'
import './parent-therapist-chat.css'

const MIN_MESSAGE_CHARS = 1
const STARTER_SNIPPET = 'Therapist chat started.'

function formatMessageTime(iso) {
  if (!iso) return ''
  const time = formatTimeIN12(iso, { suffix: '' })
  return time || ''
}

export function ParentTherapistChat({ cases = [] }) {
  const caseOptions = useMemo(() => cases.filter((c) => c?.id), [cases])
  const [caseIdOverride, setCaseIdOverride] = useState('')
  const caseId = caseIdOverride || (caseOptions[0] ? String(caseOptions[0].id) : '')
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reply, setReply] = useState('')
  const [replyFiles, setReplyFiles] = useState([])
  const [busy, setBusy] = useState(false)
  const [loopNote, setLoopNote] = useState('')
  const [showLoopIn, setShowLoopIn] = useState(false)
  const threadRef = useRef(null)
  const scrollAfterSendRef = useRef(false)

  const selectedCase = useMemo(
    () => caseOptions.find((c) => String(c.id) === String(caseId)),
    [caseOptions, caseId],
  )

  useEffect(() => {
    let active = true
    void (async () => {
      if (!caseId) {
        if (active) {
          setTicket(null)
          setLoading(false)
        }
        return
      }
      if (active) {
        setLoading(true)
        setError('')
      }
      try {
        const row = await apiFetch(`/api/v1/parent/therapist-chat?case_id=${caseId}`)
        if (!active) return
        if (!row?.id) {
          setTicket(null)
          return
        }
        const detail = await apiFetch(`/api/v1/parent/support/tickets/${row.id}`)
        if (active) setTicket(detail)
      } catch (err) {
        if (active) {
          setTicket(null)
          setError(err.message || 'Could not open therapist chat')
        }
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [caseId])

  useEffect(() => {
    if (!scrollAfterSendRef.current) return
    scrollAfterSendRef.current = false
    const el = threadRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [ticket?.messages?.length])

  const visibleMessages = useMemo(() => {
    const msgs = ticket?.messages || []
    if (msgs.length === 1 && msgs[0].body === STARTER_SNIPPET) return []
    return msgs.filter((m) => m.body !== STARTER_SNIPPET || msgs.length > 1)
  }, [ticket?.messages])

  const therapistLabel = ticket?.assigned_to_name || selectedCase?.therapist || 'Your therapist'
  const chatReady = Boolean(ticket?.id) || Boolean(caseId)

  async function postMessage(text, files = []) {
    const body = text.trim()
    if (body.length < MIN_MESSAGE_CHARS || !caseId) return
    setBusy(true)
    setError('')
    scrollAfterSendRef.current = true
    try {
      if (ticket?.id) {
        await replyParentTicket(ticket.id, body, files)
        const detail = await apiFetch(`/api/v1/parent/support/tickets/${ticket.id}`)
        setTicket(detail)
      } else {
        const detail = await apiFetch('/api/v1/parent/therapist-chat', {
          method: 'POST',
          body: JSON.stringify({ case_id: Number(caseId), message: body }),
        })
        setTicket(detail)
      }
      setReply('')
      setReplyFiles([])
    } catch (err) {
      setError(err.message || 'Could not send message')
    } finally {
      setBusy(false)
    }
  }

  function sendMessage() {
    postMessage(reply.trim(), replyFiles)
  }

  function sayHello() {
    const first = (therapistLabel || 'there').replace(/^Therapist\s+/i, '').split(/\s+/)[0]
    postMessage(`Hello${first ? `, ${first}` : ''}!`)
  }

  async function loopInCaseManager() {
    if (!ticket?.id) return
    setBusy(true)
    setError('')
    try {
      const detail = await apiFetch(`/api/v1/parent/therapist-chat/${ticket.id}/loop-in-case-manager`, {
        method: 'POST',
        body: JSON.stringify({ note: loopNote.trim() || undefined }),
      })
      setTicket(detail)
      setLoopNote('')
      setShowLoopIn(false)
    } catch (err) {
      setError(err.message || 'Could not loop in case manager')
    } finally {
      setBusy(false)
    }
  }

  if (!caseOptions.length) {
    return (
      <p className="parent-therapist-chat__empty">
        When you have an active case, you can message your therapist here.
      </p>
    )
  }

  return (
    <section className="parent-therapist-chat" aria-label="Therapist chat">
      <div className="parent-therapist-chat__header">
        <div>
          <h2 className="parent-therapist-chat__title">Therapist chat</h2>
          <p className="parent-therapist-chat__subtitle">
            Direct messages with {therapistLabel}. Need billing or tech help?{' '}
            <Link to="/parent/support">Open support</Link>.
          </p>
        </div>
        {caseOptions.length > 1 ? (
          <label className="parent-therapist-chat__case-pick">
            <span className="sr-only">Child</span>
            <select
              value={caseId}
              onChange={(e) => setCaseIdOverride(e.target.value)}
              aria-label="Select child"
            >
              {caseOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.childName}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="parent-therapist-chat__case-pill">{selectedCase?.childName}</span>
        )}
      </div>

      {loading ? (
        <p className="parent-therapist-chat__loading">Opening chat…</p>
      ) : error && !ticket && !chatReady ? (
        <p className="parent-therapist-chat__error">{error}</p>
      ) : (
        <>
          <div
            ref={threadRef}
            className={`parent-therapist-chat__thread${visibleMessages.length === 0 ? ' parent-therapist-chat__thread--empty' : ''}`}
            role="log"
            aria-live="polite"
          >
            {visibleMessages.length === 0 ? (
              <button
                type="button"
                className="parent-therapist-chat__hello"
                disabled={busy || !chatReady}
                onClick={sayHello}
              >
                {busy ? 'Sending…' : 'Say hello'}
              </button>
            ) : (
              visibleMessages.map((m) => (
                <div
                  key={m.id}
                  className={`parent-therapist-chat__msg${m.is_parent ? ' parent-therapist-chat__msg--mine' : ''}`}
                >
                  <div
                    className={`parent-therapist-chat__bubble${m.is_parent ? ' parent-therapist-chat__bubble--mine' : ''}`}
                  >
                    <p className="parent-therapist-chat__bubble-body">{m.body}</p>
                    {m.attachments?.length ? <TicketAttachmentList attachments={m.attachments} /> : null}
                  </div>
                  <time className="parent-therapist-chat__time" dateTime={m.created_at}>
                    {m.is_parent ? 'You' : m.author_name || therapistLabel} · {formatMessageTime(m.created_at)}
                  </time>
                </div>
              ))
            )}
          </div>

          {error ? <p className="parent-therapist-chat__error">{error}</p> : null}

          <div className="parent-therapist-chat__compose">
            <label className="parent-therapist-chat__input-wrap">
              <span className="sr-only">Message</span>
              <textarea
                rows={2}
                value={reply}
                placeholder={`Message ${therapistLabel}…`}
                onChange={(e) => setReply(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendMessage()
                  }
                }}
              />
            </label>
            <TicketFileInput files={replyFiles} onChange={setReplyFiles} disabled={busy} />
            <div className="parent-therapist-chat__compose-actions">
              <button
                type="button"
                className="parent-therapist-chat__send"
                disabled={busy || reply.trim().length < MIN_MESSAGE_CHARS}
                onClick={sendMessage}
              >
                {busy ? 'Sending…' : 'Send'}
              </button>
              <button
                type="button"
                className="parent-therapist-chat__secondary"
                disabled={busy || !ticket?.id}
                onClick={() => setShowLoopIn((v) => !v)}
              >
                Add case manager
              </button>
            </div>
          </div>

          {showLoopIn ? (
            <div className="parent-therapist-chat__loop-in">
              <p className="parent-therapist-chat__loop-in-lead">
                We will notify your case manager and add a note to this chat. Your therapist stays on the thread.
              </p>
              <textarea
                rows={2}
                value={loopNote}
                placeholder="Optional context for your case manager"
                onChange={(e) => setLoopNote(e.target.value)}
              />
              <button type="button" className="parent-therapist-chat__send" disabled={busy} onClick={loopInCaseManager}>
                Notify case manager
              </button>
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}
