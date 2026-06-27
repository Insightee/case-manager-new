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

export function TherapistCommunicationPage() {
  const { user } = useAuth()
  const [chats, setChats] = useState([])
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [messages, setMessages] = useState([])
  const [parentInfo, setParentInfo] = useState(null)
  const [inputText, setInputText] = useState('')
  const [sending, setSending] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [loadingChats, setLoadingChats] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)

  const selectedChat = chats.find(c => String(c.case_id) === String(selectedCaseId))

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  const loadChats = useCallback(async (selectFirst = false) => {
    setLoadingChats(true)
    setErrorMsg('')
    try {
      const data = await apiFetch('/api/v1/therapist/chats')
      setChats(data || [])
      if (data && data.length > 0 && selectFirst) {
        setSelectedCaseId(String(data[0].case_id))
      }
    } catch (err) {
      setErrorMsg(err.message || 'Could not load client list.')
    } finally {
      setLoadingChats(false)
    }
  }, [])

  const loadMessages = useCallback(async (caseId) => {
    if (!caseId) return
    setLoadingMessages(true)
    setErrorMsg('')
    try {
      const data = await apiFetch(`/api/v1/therapist/chats/${caseId}/messages`)
      setMessages(data.messages || [])
      setParentInfo(data.parent_info || null)
      
      // Update local chats list to reset unread count for the active chat
      setChats(prev => prev.map(c => 
        String(c.case_id) === String(caseId) ? { ...c, unread_count: 0 } : c
      ))
    } catch (err) {
      setErrorMsg(err.message || 'Could not fetch message history.')
    } finally {
      setLoadingMessages(false)
    }
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadChats(true)
  }, [loadChats])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadMessages(selectedCaseId)
  }, [selectedCaseId, loadMessages])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSendMessage = async (e) => {
    e.preventDefault()
    const trimmed = inputText.trim()
    if (!trimmed || sending || !selectedCaseId) return

    setSending(true)
    setErrorMsg('')

    // Optimistic message update
    const tempId = -Date.now()
    const tempMsg = {
      id: tempId,
      case_id: Number(selectedCaseId),
      sender_id: user.id,
      recipient_id: parentInfo?.id || 0,
      body: trimmed,
      is_read: false,
      created_at: new Date().toISOString()
    }

    setMessages(prev => [...prev, tempMsg])
    setInputText('')

    try {
      const saved = await apiFetch(`/api/v1/therapist/chats/${selectedCaseId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ body: trimmed })
      })
      setMessages(prev => prev.map(m => m.id === tempId ? saved : m))
    } catch (err) {
      setErrorMsg(err.message || 'Could not send message.')
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
    if (!file) return

    const MAX_SIZE = 10 * 1024 * 1024 // 10MB
    if (file.size > MAX_SIZE) {
      setErrorMsg('That photo is too large! Please select an image under 10MB.')
      return
    }

    setUploading(true)
    setErrorMsg('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const baseUrl = getApiBaseUrl()
      const { access } = getTokens()
      
      const res = await fetch(`${baseUrl}/api/v1/therapist/chats/${selectedCaseId}/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${access}`
        },
        body: formData
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Upload failed')
      }

      const savedMsg = await res.json()
      setMessages(prev => [...prev, savedMsg])
    } catch (err) {
      setErrorMsg(err.message || 'Had trouble sending your photo. Please try again.')
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
      height: 'calc(100vh - 120px)',
      background: '#f8fafc',
      fontFamily: 'Inter, system-ui, sans-serif',
      padding: '16px'
    }}>
      <div style={{
        display: 'flex',
        flexDirection: 'row',
        flex: 1,
        borderRadius: '16px',
        border: '1px solid #e2e8f0',
        overflow: 'hidden',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03)'
      }}>
        {/* Sidebar for Clients/Tabs */}
        <div style={{
          width: '320px',
          background: '#ffffff',
          borderRight: '1px solid #e2e8f0',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0
        }}>
          {/* Sidebar Header */}
          <div style={{
            padding: '20px 16px',
            borderBottom: '1px solid #e2e8f0',
            background: '#ffffff'
          }}>
            <h3 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 700, color: '#0f172a' }}>
              Conversations
            </h3>
            <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 500 }}>
              Direct back-and-forth communication
            </span>
          </div>

          {/* Client Tab List */}
          <div style={{
            flex: 1,
            overflowY: 'auto'
          }}>
            {loadingChats && chats.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>
                Loading clients...
              </div>
            ) : chats.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>
                No active client cases assigned.
              </div>
            ) : (
              chats.map((c) => {
                const isActive = String(c.case_id) === String(selectedCaseId)
                return (
                  <button
                    key={c.case_id}
                    onClick={() => setSelectedCaseId(String(c.case_id))}
                    style={{
                      width: '100%',
                      padding: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      border: 'none',
                      background: isActive ? '#f1f5f9' : '#ffffff',
                      borderBottom: '1px solid #f1f5f9',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'background 0.2s'
                    }}
                  >
                    {/* User Avatar Initial */}
                    <div style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '50%',
                      background: isActive ? '#00a884' : '#e2e8f0',
                      color: isActive ? '#ffffff' : '#475569',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '0.95rem'
                    }}>
                      {c.child_name ? c.child_name.charAt(0).toUpperCase() : 'C'}
                    </div>

                    {/* Chat Text Details */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#0f172a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {c.child_name}
                        </span>
                        {c.unread_count > 0 && (
                          <span style={{
                            background: '#ef4444',
                            color: '#ffffff',
                            borderRadius: '50%',
                            padding: '2px 6px',
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            minWidth: '18px',
                            height: '18px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}>
                            {c.unread_count}
                          </span>
                        )}
                      </div>
                      <p style={{ margin: 0, fontSize: '0.75rem', color: '#64748b', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        Parent: {c.parent_name} · {c.case_code}
                      </p>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Chat Thread Area */}
        <div style={{
          flex: 1,
          background: '#efeae2',
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0
        }}>
          {selectedChat ? (
            <>
              {/* Active Conversation Header */}
              <div style={{
                padding: '12px 20px',
                background: '#ffffff',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '50%',
                    background: '#e0f2fe',
                    color: '#0369a1',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 700,
                    fontSize: '1rem',
                    border: '1px solid #bae6fd'
                  }}>
                    {selectedChat.child_name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#0f172a' }}>
                      {selectedChat.child_name} ({selectedChat.case_code})
                    </h4>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      Parent: <strong style={{ color: '#334155' }}>{selectedChat.parent_name}</strong>
                    </span>
                  </div>
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
                  alignItems: 'center',
                  zIndex: 10
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

              {/* Scrollable Messages Panel */}
              <div style={{
                flex: 1,
                padding: '20px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}>
                {loadingMessages ? (
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                    <span style={{ fontSize: '0.875rem', color: '#64748b' }}>Loading conversation history...</span>
                  </div>
                ) : messages.length === 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', gap: '8px', padding: '0 24px', textAlign: 'center' }}>
                    <span style={{ fontSize: '1.75rem' }}>💬</span>
                    <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>
                      No messages yet. Say hello to {selectedChat.parent_name}!
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
                          maxWidth: '70%',
                          background: isMe ? '#d9fdd3' : '#ffffff',
                          color: '#0f172a',
                          padding: '8px 12px',
                          borderRadius: isMe ? '12px 0 12px 12px' : '0 12px 12px 12px',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
                          position: 'relative',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px'
                        }}
                      >
                        <ChatImage attachmentId={msg.id} alt={msg.attachment_name} />
                        <span style={{
                          alignSelf: 'flex-end',
                          fontSize: '0.65rem',
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

              {/* Chat Input Footer */}
              <form
                onSubmit={handleSendMessage}
                style={{
                  padding: '12px 20px',
                  background: '#f0f2f5',
                  borderTop: '1px solid #e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px'
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
                  disabled={uploading}
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
                    opacity: uploading ? 0.5 : 1
                  }}
                  title="Send photo"
                >
                  📎
                </button>

                <input
                  type="text"
                  placeholder="Type a message..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  disabled={sending || uploading}
                  style={{
                    flex: 1,
                    padding: '10px 16px',
                    fontSize: '0.875rem',
                    borderRadius: '24px',
                    border: 'none',
                    outline: 'none',
                    background: '#ffffff',
                    color: '#1e293b'
                  }}
                />

                <button
                  type="submit"
                  disabled={sending || uploading || !inputText.trim()}
                  style={{
                    border: 'none',
                    background: inputText.trim() ? '#00a884' : '#a0a0a0',
                    color: '#ffffff',
                    width: '40px',
                    height: '40px',
                    borderRadius: '50%',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.875rem',
                    transition: 'background 0.2s',
                    opacity: !inputText.trim() ? 0.6 : 1
                  }}
                >
                  {sending ? '...' : '▶'}
                </button>
              </form>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', gap: '12px', padding: '0 24px', textAlign: 'center' }}>
              <span style={{ fontSize: '2.5rem' }}>💬</span>
              <h4 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 600, color: '#0f172a' }}>
                Select a client to start chatting
              </h4>
              <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b', maxWidth: '320px' }}>
                Choose one of your active client cases from the left panel to access back-and-forth updates.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
