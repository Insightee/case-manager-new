import { useEffect, useState, useRef, useCallback } from 'react'
import { apiFetch, getTokens, getApiBaseUrl } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'

function ChatImage({ attachmentId, downloadPrefix = '/api/v1/parent/chats/messages/attachments', alt = 'Photo' }) {
  const [src, setSrc] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    const { access } = getTokens()
    const baseUrl = getApiBaseUrl()
    const url = `${baseUrl}${downloadPrefix}/${attachmentId}`

    fetch(url, {
      headers: {
        Authorization: `Bearer ${access}`,
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load image')
        return res.blob()
      })
      .then((blob) => {
        if (active) {
          const objectUrl = URL.createObjectURL(blob)
          setSrc(objectUrl)
          setLoading(false)
        }
      })
      .catch((err) => {
        console.error(err)
        if (active) {
          setError(true)
          setLoading(false)
        }
      })

    return () => {
      active = false
      if (src) {
        URL.revokeObjectURL(src)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachmentId, downloadPrefix])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 180, height: 130, background: '#f1f5f9', borderRadius: 8 }}>
        <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Loading image...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 180, height: 130, background: '#fee2e2', borderRadius: 8 }}>
        <span style={{ fontSize: '0.75rem', color: '#ef4444' }}>Failed to load image</span>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      style={{ maxWidth: '100%', maxHeight: 240, borderRadius: 8, objectFit: 'contain', cursor: 'pointer', display: 'block', marginTop: 4 }}
      onClick={() => window.open(src, '_blank')}
    />
  )
}

export function ParentUpdatesChat({ cases = [] }) {
  const { user } = useAuth()
  const activeCases = cases.filter(c => c.id) // Ensure we have valid DB IDs

  const [selectedCaseId, setSelectedCaseId] = useState(() => {
    return activeCases[0]?.id || ''
  })
  
  const [messages, setMessages] = useState([])
  const [activeTherapists, setActiveTherapists] = useState([])
  const [selectedTherapistId, setSelectedTherapistId] = useState('')
  const [activeTherapist, setActiveTherapist] = useState(null)
  const [inputText, setInputText] = useState('')
  const [sending, setSending] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [loading, setLoading] = useState(false)

  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)

  const selectedCase = activeCases.find(c => String(c.id) === String(selectedCaseId))

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  const loadChat = useCallback(async (caseId, therapistId) => {
    if (!caseId) return
    setLoading(true)
    setErrorMsg('')
    try {
      const url = `/api/v1/parent/chats/${caseId}/messages` + (therapistId ? `?therapist_id=${therapistId}` : '')
      const data = await apiFetch(url)
      setMessages(data.messages || [])
      setActiveTherapists(data.active_therapists || [])
      setActiveTherapist(data.active_therapist || null)
      
      const fetchedTherapistId = data.selected_therapist_id ? String(data.selected_therapist_id) : ''
      if (fetchedTherapistId !== String(therapistId)) {
        setSelectedTherapistId(fetchedTherapistId)
      }
    } catch (err) {
      setErrorMsg(err.message || 'We could not fetch your chat messages.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeCases.length > 0 && !selectedCaseId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedCaseId(String(activeCases[0].id))
    }
  }, [activeCases, selectedCaseId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedTherapistId('')
  }, [selectedCaseId])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadChat(selectedCaseId, selectedTherapistId)
  }, [selectedCaseId, selectedTherapistId, loadChat])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSendMessage = async (e) => {
    e.preventDefault()
    const trimmed = inputText.trim()
    if (!trimmed || sending || !selectedCaseId || !selectedTherapistId) return

    setSending(true)
    setErrorMsg('')

    // Optimistic message update
    const tempId = -Date.now()
    const tempMsg = {
      id: tempId,
      case_id: Number(selectedCaseId),
      sender_id: user.id,
      recipient_id: Number(selectedTherapistId),
      body: trimmed,
      is_read: false,
      created_at: new Date().toISOString()
    }

    setMessages(prev => [...prev, tempMsg])
    setInputText('')

    try {
      const saved = await apiFetch(`/api/v1/parent/chats/${selectedCaseId}/messages?therapist_id=${selectedTherapistId}`, {
        method: 'POST',
        body: JSON.stringify({ body: trimmed })
      })
      setMessages(prev => prev.map(m => m.id === tempId ? saved : m))
    } catch (err) {
      setErrorMsg(err.message || 'We could not send your message. Let\'s try again.')
      setMessages(prev => prev.filter(m => m.id !== tempId))
    } finally {
      setSending(false)
    }
  }

  const handleAttachClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file || !selectedTherapistId) return

    const MAX_SIZE = 10 * 1024 * 1024 // 10MB
    if (file.size > MAX_SIZE) {
      setErrorMsg('That photo is a bit too large! Please choose a photo smaller than 10MB so we can share it easily.')
      return
    }

    setUploading(true)
    setErrorMsg('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const baseUrl = getApiBaseUrl()
      const { access } = getTokens()
      
      const res = await fetch(`${baseUrl}/api/v1/parent/chats/${selectedCaseId}/upload?therapist_id=${selectedTherapistId}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${access}`
        },
        body: formData
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to upload image')
      }

      const savedMsg = await res.json()
      setMessages(prev => [...prev, savedMsg])
    } catch (err) {
      setErrorMsg(err.message || 'We had trouble uploading your photo. Please try again.')
    } finally {
      setUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '600px',
      maxHeight: '80vh',
      borderRadius: '16px',
      overflow: 'hidden',
      border: '1px solid #e2e8f0',
      background: '#efeae2',
      fontFamily: 'Inter, system-ui, sans-serif'
    }}>
      {/* Top Case / Therapist Selector Header */}
      <div style={{
        padding: '12px 16px',
        background: '#fff',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Child Case:</span>
            <select
              id="chat-case-select"
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.875rem',
                color: '#1e293b',
                fontWeight: 500,
                outline: 'none',
                background: '#f8fafc'
              }}
            >
              {activeCases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.childName} ({c.caseId})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Therapist:</span>
            <select
              id="chat-therapist-select"
              value={selectedTherapistId}
              onChange={(e) => setSelectedTherapistId(e.target.value)}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.875rem',
                color: '#1e293b',
                fontWeight: 500,
                outline: 'none',
                background: '#f8fafc'
              }}
              disabled={activeTherapists.length === 0}
            >
              {activeTherapists.length === 0 ? (
                <option value="">Unassigned</option>
              ) : (
                activeTherapists.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.full_name}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        {selectedCase && (
          <div style={{ fontSize: '0.875rem', color: '#64748b' }}>
            Service Type: <strong style={{ color: '#0f172a' }}>{selectedCase.serviceType}</strong>
          </div>
        )}
      </div>

      {/* Recipient / Therapist Header Info */}
      <div style={{
        padding: '10px 16px',
        background: '#f8fafc',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        {/* Recipient Avatar */}
        <div style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          background: '#d9fdd3',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 700,
          color: '#15803d',
          fontSize: '1rem',
          border: '1px solid #bbf7d0'
        }}>
          {activeTherapist?.full_name ? activeTherapist.full_name.charAt(0).toUpperCase() : 'T'}
        </div>
        <div>
          <h4 style={{ margin: 0, fontSize: '0.925rem', fontWeight: 600, color: '#0f172a' }}>
            {activeTherapist?.full_name ? activeTherapist.full_name : 'No active therapist linked'}
          </h4>
          <span style={{ fontSize: '0.75rem', color: activeTherapist ? '#16a34a' : '#ef4444', fontWeight: 500 }}>
            {activeTherapist ? '● Active Therapist' : 'Unassigned'}
          </span>
        </div>
      </div>

      {/* Error Banner */}
      {errorMsg && (
        <div style={{
          padding: '10px 16px',
          background: '#fee2e2',
          borderBottom: '1px solid #fecaca',
          fontSize: '0.8125rem',
          color: '#b91c1c',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>{errorMsg}</span>
          <button
            onClick={() => setErrorMsg('')}
            style={{ border: 'none', background: 'none', color: '#b91c1c', cursor: 'pointer', fontWeight: 'bold' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Message Body Area */}
      <div style={{
        flex: 1,
        padding: '16px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <span style={{ fontSize: '0.875rem', color: '#64748b' }}>Loading messages...</span>
          </div>
        ) : messages.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', gap: '8px', padding: '0 24px', textAlign: 'center' }}>
            <span style={{ fontSize: '1.5rem' }}>💬</span>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
              No messages yet. Send a message to start communicating with your therapist.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            const isMe = msg.sender_id === user.id
            const timeStr = msg.created_at
              ? new Date(msg.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
              : ''

            return (
              <div
                key={msg.id}
                style={{
                  alignSelf: isMe ? 'flex-end' : 'flex-start',
                  maxWidth: '75%',
                  background: isMe ? '#d9fdd3' : '#ffffff',
                  color: '#0f172a',
                  padding: '8px 12px',
                  borderRadius: isMe ? '12px 0 12px 12px' : '0 12px 12px 12px',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                {/* Attachment check */}
                {msg.attachment_path ? (
                  <ChatImage attachmentId={msg.id} alt={msg.attachment_name} />
                ) : (
                  <p style={{ margin: 0, fontSize: '0.875rem', whiteSpace: 'pre-wrap', lineHeight: '1.4' }}>
                    {msg.body}
                  </p>
                )}

                <span style={{
                  alignSelf: 'flex-end',
                  fontSize: '0.6875rem',
                  color: '#64748b',
                  marginTop: '2px'
                }}>
                  {timeStr} {isMe && (msg.is_read ? '✓✓' : '✓')}
                </span>
              </div>
            )
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Footnote / 90 Days Limit Info */}
      <div style={{
        textAlign: 'center',
        padding: '6px 12px',
        fontSize: '0.72rem',
        color: '#64748b',
        background: '#f1f5f9',
        borderTop: '1px solid #e2e8f0',
        fontWeight: 500
      }}>
        🔒 Messages are deleted automatically after 90 days.
      </div>

      {/* Bottom Chat Input Bar */}
      <form
        onSubmit={handleSendMessage}
        style={{
          padding: '10px 16px',
          background: '#f0f2f5',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          borderTop: '1px solid #e2e8f0'
        }}
      >
        <input
          type="file"
          accept="image/*"
          ref={fileInputRef}
          onChange={handleFileUpload}
          style={{ display: 'none' }}
        />

        <button
          type="button"
          onClick={handleAttachClick}
          disabled={uploading || !activeTherapist}
          style={{
            border: 'none',
            background: 'none',
            fontSize: '1.25rem',
            color: '#54656f',
            cursor: 'pointer',
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: (!activeTherapist || uploading) ? 0.5 : 1
          }}
          title="Send photo"
        >
          📎
        </button>

        <input
          type="text"
          placeholder={activeTherapist ? "Type a message..." : "Assign active therapist to send messages"}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={sending || uploading || !activeTherapist}
          style={{
            flex: 1,
            padding: '9px 14px',
            fontSize: '0.875rem',
            borderRadius: '20px',
            border: 'none',
            outline: 'none',
            background: '#ffffff',
            color: '#1e293b'
          }}
        />

        <button
          type="submit"
          disabled={sending || uploading || !inputText.trim() || !activeTherapist}
          style={{
            border: 'none',
            background: (inputText.trim() && activeTherapist) ? '#00a884' : '#a0a0a0',
            color: '#ffffff',
            width: '38px',
            height: '38px',
            borderRadius: '50%',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.875rem',
            fontWeight: 'bold',
            transition: 'background 0.2s',
            opacity: (!inputText.trim() || !activeTherapist) ? 0.6 : 1
          }}
        >
          {sending ? '...' : '▶'}
        </button>
      </form>
    </div>
  )
}
