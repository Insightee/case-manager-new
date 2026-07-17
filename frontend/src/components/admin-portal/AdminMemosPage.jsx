import { useEffect, useState, useMemo } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import { MemoThreadDrawer } from '../support/MemoThreadDrawer.jsx'

export function AdminMemosPage() {
  const [memos, setMemos] = useState([])
  const [stats, setStats] = useState({ open: 0, pending_reply: 0, under_review: 0, closed_this_month: 0 })
  const [recipients, setRecipients] = useState([])
  const [recipientSearch, setRecipientSearch] = useState('')
  const [loading, setLoading] = useState(true)
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const [priorityFilter, setPriorityFilter] = useState('ALL')
  const [monthFilter, setMonthFilter] = useState('ALL')

  // Modals & Drawers
  const [showIssueModal, setShowIssueModal] = useState(false)
  const [selectedMemoId, setSelectedMemoId] = useState(null)
  const [memoDetail, setMemoDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Memo Issuance Form State
  const [form, setForm] = useState({
    category: 'Performance',
    priority: 'Medium',
    recipient_type: 'Therapist',
    recipient_ids: [],
    bulk_target: '',
    subject: '',
    details: '',
    reply_required: false,
    acknowledgement_only: false,
    due_date: '',
  })
  const [formFiles, setFormFiles] = useState([])
  const [formError, setFormError] = useState('')
  const [formSuccess, setFormSuccess] = useState('')
  const [issuing, setIssuing] = useState(false)

  // Reply Form State
  const [replyText, setReplyText] = useState('')
  const [replyFiles, setReplyFiles] = useState([])
  const [replyError, setReplyError] = useState('')
  const [replying, setReplying] = useState(false)

  // Load memo list and stats
  async function loadData() {
    setLoading(true)
    try {
      const qs = new URLSearchParams()
      if (statusFilter !== 'ALL') qs.set('status', statusFilter)
      if (categoryFilter !== 'ALL') qs.set('category', categoryFilter)
      if (priorityFilter !== 'ALL') qs.set('priority', priorityFilter)
      if (monthFilter !== 'ALL') qs.set('month', monthFilter)
      if (searchQuery) qs.set('search', searchQuery)

      const [list, metrics] = await Promise.all([
        apiFetch(`/api/v1/memos?${qs.toString()}`),
        apiFetch('/api/v1/memos/stats')
      ])
      setMemos(list || [])
      setStats(metrics || { open: 0, pending_reply: 0, under_review: 0, closed_this_month: 0 })
    } catch (err) {
      console.error('Could not load memos', err)
    } finally {
      setLoading(false)
    }
  }

  // Load recipient candidates
  async function loadRecipients(q = '') {
    try {
      const data = await apiFetch(`/api/v1/memos/recipients${q ? '?search=' + encodeURIComponent(q) : ''}`)
      setRecipients(data || [])
    } catch {
      setRecipients([])
    }
  }

  useEffect(() => {
    loadData()
  }, [statusFilter, categoryFilter, priorityFilter, monthFilter, searchQuery])

  useEffect(() => {
    if (showIssueModal) {
      loadRecipients('')
    }
  }, [showIssueModal])

  // Fetch memo detail when selected
  async function loadMemoDetail(id) {
    setDetailLoading(true)
    setMemoDetail(null)
    setReplyText('')
    setReplyFiles([])
    setReplyError('')
    try {
      const data = await apiFetch(`/api/v1/memos/${id}`)
      setMemoDetail(data)
    } catch (err) {
      console.error(err)
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    if (selectedMemoId) {
      loadMemoDetail(selectedMemoId)
    } else {
      setMemoDetail(null)
    }
  }, [selectedMemoId])

  // Handle Export CSV
  async function exportCsv() {
    try {
      const res = await apiFetch('/api/v1/memos/export')
      const blob = new Blob([res], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.setAttribute('href', url)
      a.setAttribute('download', `memos-report-${new Date().toISOString().slice(0, 10)}.csv`)
      a.click()
    } catch (err) {
      alert('Export failed: ' + err.message)
    }
  }

  // Submit new memo
  async function submitIssueMemo(e) {
    e.preventDefault()
    if (!form.bulk_target && form.recipient_ids.length === 0) {
      setFormError('Please select at least one recipient or a bulk target.')
      return
    }
    setIssuing(true)
    setFormError('')
    setFormSuccess('')

    try {
      const formData = new FormData()
      formData.append('category', form.category)
      formData.append('priority', form.priority)
      formData.append('recipient_type', form.recipient_type)
      formData.append('subject', form.subject)
      formData.append('details', form.details)
      formData.append('reply_required', String(form.reply_required))
      formData.append('acknowledgement_only', String(form.acknowledgement_only))
      if (form.due_date) formData.append('due_date', form.due_date)
      if (form.bulk_target) formData.append('bulk_target', form.bulk_target)
      formData.append('recipient_ids', JSON.stringify(form.recipient_ids))

      formFiles.forEach((file) => {
        formData.append('files', file)
      })

      await apiFetch('/api/v1/memos', {
        method: 'POST',
        body: formData,
      })

      setFormSuccess('Memo issued successfully!')
      setForm({
        category: 'Performance',
        priority: 'Medium',
        recipient_type: 'Therapist',
        recipient_ids: [],
        bulk_target: '',
        subject: '',
        details: '',
        reply_required: false,
        acknowledgement_only: false,
        due_date: '',
      })
      setFormFiles([])
      setTimeout(() => {
        setShowIssueModal(false)
        setFormSuccess('')
        loadData()
      }, 1000)
    } catch (err) {
      setFormError(err.message || 'Failed to issue memo')
    } finally {
      setIssuing(false)
    }
  }

  // Submit reply message
  async function submitReply(e) {
    e.preventDefault()
    if (!replyText.trim()) return
    setReplying(true)
    setReplyError('')

    try {
      const formData = new FormData()
      formData.append('body', replyText)
      replyFiles.forEach((file) => {
        formData.append('files', file)
      })

      await apiFetch(`/api/v1/memos/${selectedMemoId}/messages`, {
        method: 'POST',
        body: formData,
      })

      setReplyText('')
      setReplyFiles([])
      await loadMemoDetail(selectedMemoId)
      loadData()
    } catch (err) {
      setReplyError(err.message || 'Could not send message')
    } finally {
      setReplying(false)
    }
  }

  // Close Memo
  async function handleCloseMemo() {
    if (!window.confirm('Are you sure you want to close this memo thread?')) return
    try {
      await apiFetch(`/api/v1/memos/${selectedMemoId}/close`, { method: 'POST' })
      await loadMemoDetail(selectedMemoId)
      loadData()
    } catch (err) {
      alert(err.message)
    }
  }

  // Reopen Memo
  async function handleReopenMemo() {
    try {
      await apiFetch(`/api/v1/memos/${selectedMemoId}/reopen`, { method: 'POST' })
      await loadMemoDetail(selectedMemoId)
      loadData()
    } catch (err) {
      alert(err.message)
    }
  }

  // Toggle recipient selection
  function toggleRecipient(id) {
    setForm((f) => {
      const ids = f.recipient_ids.includes(id)
        ? f.recipient_ids.filter((x) => x !== id)
        : [...f.recipient_ids, id]
      return { ...f, recipient_ids: ids }
    })
  }

  // Render stats status colors
  const statusColors = {
    OPEN: { bg: '#eef2ff', color: '#4f46e5', label: 'Open' },
    PENDING_REPLY: { bg: '#fffbeb', color: '#d97706', label: 'Pending Reply' },
    UNDER_REVIEW: { bg: '#f0fdf4', color: '#16a34a', label: 'Under Review' },
    CLOSED: { bg: '#f3f4f6', color: '#4b5563', label: 'Closed' }
  }

  const priorityColors = {
    Low: '#9ca3af',
    Medium: '#eab308',
    High: '#ef4444'
  }

  const filteredRecipients = recipients.filter((r) => {
    // Filter based on Recipient Type
    if (form.recipient_type === 'Therapist' && !r.roles.includes('THERAPIST')) return false
    if (form.recipient_type === 'Case Manager' && !r.roles.includes('CASE_MANAGER')) return false
    if (form.recipient_type === 'Admin' && !r.roles.includes('ADMIN') && !r.roles.includes('SUPER_ADMIN') && !r.roles.includes('MODULE_ADMIN') && !r.roles.includes('HR') && !r.roles.includes('FINANCE')) return false
    if (form.recipient_type === 'Mentor' && !r.roles.includes('SUPERVISOR')) return false // Supervisor is Mentor role in perm mapping
    return true
  })

  return (
    <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* 1. Stats Dashboard Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Open Memos</p>
          <p style={{ fontSize: '2rem', fontWeight: 700, color: '#1e293b', margin: '0.5rem 0 0 0' }}>{stats.open}</p>
        </div>
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Pending Replies</p>
          <p style={{ fontSize: '2rem', fontWeight: 700, color: '#d97706', margin: '0.5rem 0 0 0' }}>{stats.pending_reply}</p>
        </div>
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Under Review</p>
          <p style={{ fontSize: '2rem', fontWeight: 700, color: '#16a34a', margin: '0.5rem 0 0 0' }}>{stats.under_review}</p>
        </div>
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>Closed This Month</p>
          <p style={{ fontSize: '2rem', fontWeight: 700, color: '#4b5563', margin: '0.5rem 0 0 0' }}>{stats.closed_this_month}</p>
        </div>
      </div>

      {/* 2. Actions and Filter Toolbar */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', background: '#fff', padding: '1rem', border: '1px solid #e2e8f0', borderRadius: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', gap: '8px', flex: 1, minWidth: 260 }}>
            <input
              type="text"
              placeholder="Search memo code, subject, or name…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: 1, padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 8, fontSize: '0.875rem' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={exportCsv}
              style={{ background: '#f8fafc', border: '1px solid #cbd5e1', color: '#334155', padding: '8px 14px', borderRadius: 8, fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}
            >
              Export Report
            </button>
            <button
              onClick={() => { setShowIssueModal(true); setFormError(''); setFormSuccess('') }}
              style={{ background: '#6366f1', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: 8, fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}
            >
              + Issue Memo
            </button>
          </div>
        </div>

        {/* Collapsible filters block */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px', pt: '10px', borderTop: '1px solid #f1f5f9' }}>
          <div>
            <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>Status</label>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: '100%', padding: '6px', border: '1px solid #cbd5e1', borderRadius: 6, marginTop: 4 }}>
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="PENDING_REPLY">Pending Reply</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="CLOSED">Closed</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>Category</label>
            <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} style={{ width: '100%', padding: '6px', border: '1px solid #cbd5e1', borderRadius: 6, marginTop: 4 }}>
              <option value="ALL">All Categories</option>
              <option value="Performance">Performance</option>
              <option value="Compliance">Compliance</option>
              <option value="Administrative">Administrative</option>
              <option value="Training">Training</option>
              <option value="Documentation">Documentation</option>
              <option value="Attendance">Attendance</option>
              <option value="Other">Other</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>Priority</label>
            <select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} style={{ width: '100%', padding: '6px', border: '1px solid #cbd5e1', borderRadius: 6, marginTop: 4 }}>
              <option value="ALL">All Priorities</option>
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>Month</label>
            <select value={monthFilter} onChange={(e) => setMonthFilter(e.target.value)} style={{ width: '100%', padding: '6px', border: '1px solid #cbd5e1', borderRadius: 6, marginTop: 4 }}>
              <option value="ALL">All Months</option>
              <option value="1">January</option>
              <option value="2">February</option>
              <option value="3">March</option>
              <option value="4">April</option>
              <option value="5">May</option>
              <option value="6">June</option>
              <option value="7">July</option>
              <option value="8">August</option>
              <option value="9">September</option>
              <option value="10">October</option>
              <option value="11">November</option>
              <option value="12">December</option>
            </select>
          </div>
        </div>
      </div>

      {/* 3. Memos Grid List View */}
      <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>Loading memos…</div>
        ) : memos.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b' }}>
            <p style={{ fontWeight: 600, fontSize: '1rem', margin: 0 }}>No memos found</p>
            <p style={{ fontSize: '0.875rem', color: '#94a3b8', marginTop: 4 }}>Adjust filters or issue a new compliance memo.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569' }}>Memo ID</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569' }}>Recipient</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569' }}>Subject</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569' }}>Category</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569' }}>Priority</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569' }}>Status</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569' }}>Created On</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: '#475569', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {memos.map((m) => {
                  const badge = statusColors[m.status] || { bg: '#f1f5f9', color: '#475569', label: m.status }
                  return (
                    <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9', hover: { background: '#f8fafc' } }}>
                      <td style={{ padding: '14px 16px', fontWeight: 600, color: '#334155' }}>{m.memo_code}</td>
                      <td style={{ padding: '14px 16px', color: '#0f172a' }}>{m.recipient_name}</td>
                      <td style={{ padding: '14px 16px', color: '#334155', fontWeight: 500 }}>{m.subject}</td>
                      <td style={{ padding: '14px 16px', color: '#475569' }}>{m.category}</td>
                      <td style={{ padding: '14px 16px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: priorityColors[m.priority] || '#ccc' }}></span>
                          {m.priority}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '4px 8px', borderRadius: 6, background: badge.bg, color: badge.color }}>
                          {badge.label}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', color: '#64748b' }}>{new Date(m.created_at).toLocaleDateString()}</td>
                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <button
                          onClick={() => setSelectedMemoId(m.id)}
                          style={{ background: 'none', border: 'none', color: '#4f46e5', fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem' }}
                        >
                          View Thread
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 4. Issue Memo Modal */}
      {showIssueModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(15, 23, 42, 0.4)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 16 }}>
          <div style={{ background: '#fff', borderRadius: 16, width: '100%', maxWidth: 650, maxHeight: '90vh', overflowY: 'auto', padding: '1.75rem', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid #f1f5f9', pb: '10px' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: '#1e293b' }}>Issue Memo</h3>
              <button onClick={() => setShowIssueModal(false)} style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: '#94a3b8' }}>&times;</button>
            </div>

            {formError ? <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', padding: '10px', borderRadius: 8, color: '#b91c1c', fontSize: '0.875rem', marginBottom: '1rem' }}>{formError}</div> : null}
            {formSuccess ? <div style={{ background: '#f0fdf4', border: '1px solid #86efac', padding: '10px', borderRadius: 8, color: '#16a34a', fontSize: '0.875rem', marginBottom: '1rem' }}>{formSuccess}</div> : null}

            <form onSubmit={submitIssueMemo} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Memo Category</label>
                  <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4 }}>
                    <option value="Performance">Performance</option>
                    <option value="Compliance">Compliance</option>
                    <option value="Administrative">Administrative</option>
                    <option value="Training">Training</option>
                    <option value="Documentation">Documentation</option>
                    <option value="Attendance">Attendance</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Priority</label>
                  <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4 }}>
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Recipient Type</label>
                  <select
                    value={form.recipient_type}
                    onChange={(e) => setForm({ ...form, recipient_type: e.target.value, recipient_ids: [], bulk_target: '' })}
                    style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4 }}
                  >
                    <option value="Therapist">Therapist</option>
                    <option value="Case Manager">Case Manager</option>
                    <option value="Admin">Admin</option>
                    <option value="Mentor">Mentor</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Bulk Target (Optional)</label>
                  <select
                    value={form.bulk_target}
                    onChange={(e) => setForm({ ...form, bulk_target: e.target.value, recipient_ids: [] })}
                    style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4 }}
                  >
                    <option value="">— Individual Selection —</option>
                    {form.recipient_type === 'Therapist' && (
                      <>
                        <option value="ALL_HOMECARE_THERAPISTS">All Homecare Therapists</option>
                        <option value="ALL_SHADOW_THERAPISTS">All Shadow Therapists</option>
                      </>
                    )}
                    {form.recipient_type === 'Case Manager' && (
                      <option value="ALL_CASE_MANAGERS">All Case Managers</option>
                    )}
                  </select>
                </div>
              </div>

              {!form.bulk_target && (
                <div>
                  <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Select Recipient(s)</label>
                  <input
                    type="text"
                    placeholder="Filter names…"
                    value={recipientSearch}
                    onChange={(e) => { setRecipientSearch(e.target.value); loadRecipients(e.target.value) }}
                    style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4, boxSizing: 'border-box' }}
                  />
                  <div style={{ border: '1px solid #cbd5e1', borderRadius: 8, maxHeight: 150, overflowY: 'auto', padding: 8, marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {filteredRecipients.length === 0 ? (
                      <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '4px auto' }}>No matches found</p>
                    ) : (
                      filteredRecipients.map((r) => (
                        <label
                          key={r.id}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: '0.8rem',
                            padding: '4px 8px',
                            background: form.recipient_ids.includes(r.id) ? '#eef2ff' : '#f8fafc',
                            border: form.recipient_ids.includes(r.id) ? '1px solid #818cf8' : '1px solid #e2e8f0',
                            borderRadius: 20,
                            cursor: 'pointer'
                          }}
                        >
                          <input type="checkbox" checked={form.recipient_ids.includes(r.id)} onChange={() => toggleRecipient(r.id)} />
                          {r.full_name}
                        </label>
                      ))
                    )}
                  </div>
                </div>
              )}

              <div>
                <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Subject</label>
                <input
                  type="text"
                  required
                  value={form.subject}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4, boxSizing: 'border-box' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Details</label>
                <textarea
                  required
                  rows={5}
                  value={form.details}
                  onChange={(e) => setForm({ ...form, details: e.target.value })}
                  placeholder="Memo details (Rich text editor simulation)..."
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4, boxSizing: 'border-box', fontFamily: 'inherit', resize: 'vertical' }}
                />
              </div>

              {/* File Upload Zone */}
              <div>
                <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Attachments</label>
                <input
                  type="file"
                  multiple
                  onChange={(e) => setFormFiles(Array.from(e.target.files || []))}
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4, boxSizing: 'border-box' }}
                />
              </div>

              {/* Requirement Checkboxes */}
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.875rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.reply_required}
                    onChange={(e) => setForm({ ...form, reply_required: e.target.checked, acknowledgement_only: e.target.checked ? false : form.acknowledgement_only })}
                  />
                  Reply Required
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.875rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.acknowledgement_only}
                    onChange={(e) => setForm({ ...form, acknowledgement_only: e.target.checked, reply_required: e.target.checked ? false : form.reply_required })}
                  />
                  Acknowledgement Only
                </label>
              </div>

              <div>
                <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569' }}>Reply Due Date</label>
                <input
                  type="date"
                  className="admin-input"
                  value={form.due_date}
                  onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, marginTop: 4, boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 10 }}>
                <button type="button" onClick={() => setShowIssueModal(false)} style={{ background: '#f1f5f9', border: '1px solid #cbd5e1', padding: '8px 16px', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>
                  Cancel
                </button>
                <button type="submit" disabled={issuing} style={{ background: '#6366f1', color: '#fff', border: 'none', padding: '8px 18px', borderRadius: 8, fontWeight: 600, cursor: 'pointer', opacity: issuing ? 0.7 : 1 }}>
                  {issuing ? 'Issuing…' : 'Issue Memo'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <MemoThreadDrawer
        open={Boolean(selectedMemoId)}
        onClose={() => setSelectedMemoId(null)}
        memoCode={memoDetail?.memo_code}
        title="Memo Thread"
        loading={detailLoading || !memoDetail}
        memoPreview={
          memoDetail ? (
            <>
              <div className="memo-thread-drawer__preview-badges">
                <span className="memo-thread-drawer__preview-badge" style={{ background: '#f1f5f9', color: '#475569' }}>
                  {memoDetail.category}
                </span>
                <span className="memo-thread-drawer__preview-badge" style={{ background: '#fee2e2', color: '#ef4444' }}>
                  {memoDetail.priority}
                </span>
                <span
                  className="memo-thread-drawer__preview-badge"
                  style={{
                    background: statusColors[memoDetail.status]?.bg || '#f1f5f9',
                    color: statusColors[memoDetail.status]?.color || '#475569',
                  }}
                >
                  {statusColors[memoDetail.status]?.label || memoDetail.status}
                </span>
              </div>
              <p className="memo-thread-drawer__preview-subject">{memoDetail.subject}</p>
              <p className="memo-thread-drawer__preview-meta">
                From {memoDetail.sender?.full_name || 'System'} · To {memoDetail.recipient?.full_name}
              </p>
            </>
          ) : null
        }
        memoSection={
          memoDetail ? (
            <>
              <p style={{ fontSize: '0.875rem', color: '#334155', whiteSpace: 'pre-wrap', lineHeight: 1.5, background: '#fff', padding: 12, borderRadius: 8, border: '1px solid #e2e8f0', margin: 0 }}>
                {memoDetail.details}
              </p>
              {memoDetail.attachments?.length > 0 ? (
                <div style={{ marginTop: 12 }}>
                  <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569', margin: '0 0 6px 0' }}>Attachments:</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {memoDetail.attachments.map((a) => (
                      <a
                        key={a.id}
                        href={`/api/v1/memos/${memoDetail.id}/attachments/${a.id}`}
                        download
                        style={{ fontSize: '0.8rem', color: '#4f46e5', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                      >
                        📎 {a.file_name}{' '}
                        <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>({(a.size_bytes / 1024).toFixed(1)} KB)</span>
                      </a>
                    ))}
                  </div>
                </div>
              ) : null}
              {memoDetail.due_date ? (
                <div style={{ marginTop: 12, fontSize: '0.8rem', color: '#b45309', fontWeight: 500 }}>
                  ⚠️ Response Due Date: {new Date(memoDetail.due_date).toLocaleDateString()}
                </div>
              ) : null}
            </>
          ) : null
        }
        timelineSection={
          memoDetail ? (
            <>
              {memoDetail.audit_logs?.map((l) => (
                <div key={`log-${l.id}`} style={{ display: 'flex', gap: 8, fontSize: '0.75rem', color: '#64748b', padding: '4px 0' }}>
                  <span style={{ color: '#94a3b8' }}>[{new Date(l.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}]</span>
                  <span>
                    <strong>{l.actor_name}</strong>{' '}
                    {l.action === 'created'
                      ? 'issued memo'
                      : l.action === 'viewed'
                        ? 'opened memo'
                        : l.action === 'replied'
                          ? 'submitted reply'
                          : l.action === 'acknowledged'
                            ? 'acknowledged memo'
                            : l.action}
                  </span>
                  {l.details ? <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>({l.details})</span> : null}
                </div>
              ))}
              {memoDetail.messages?.map((msg) => (
                <div
                  key={`msg-${msg.id}`}
                  style={{
                    alignSelf: msg.author.id === memoDetail.recipient?.id ? 'flex-start' : 'flex-end',
                    background: msg.author.id === memoDetail.recipient?.id ? '#fff' : '#eef2ff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    padding: '10px 12px',
                    maxWidth: '85%',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 4 }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#1e293b' }}>{msg.author.full_name}</span>
                    <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>{new Date(msg.created_at).toLocaleDateString()}</span>
                  </div>
                  <p style={{ fontSize: '0.85rem', color: '#334155', margin: 0, whiteSpace: 'pre-wrap' }}>{msg.body}</p>
                  {msg.attachments?.map((a) => (
                    <div key={a.id} style={{ marginTop: 6, borderTop: '1px solid #f1f5f9', paddingTop: 4 }}>
                      <a
                        href={`/api/v1/memos/${memoDetail.id}/attachments/${a.id}`}
                        download
                        style={{ fontSize: '0.75rem', color: '#4f46e5', textDecoration: 'none' }}
                      >
                        📎 {a.file_name}
                      </a>
                    </div>
                  ))}
                </div>
              ))}
            </>
          ) : null
        }
        footer={
          memoDetail ? (
            memoDetail.status === 'CLOSED' ? (
              <div style={{ textAlign: 'center' }}>
                <p style={{ fontSize: '0.875rem', color: '#64748b', margin: '0 0 10px 0' }}>This memo is Closed.</p>
                <button
                  type="button"
                  onClick={handleReopenMemo}
                  style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: 6, fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer' }}
                >
                  Reopen Memo Thread
                </button>
              </div>
            ) : (
              <form onSubmit={submitReply} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {replyError ? <div style={{ fontSize: '0.75rem', color: '#ef4444' }}>{replyError}</div> : null}
                <textarea
                  rows={2}
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type your response/clarification here…"
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid #cbd5e1', borderRadius: 8, boxSizing: 'border-box', fontFamily: 'inherit', resize: 'none' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <input
                    type="file"
                    multiple
                    onChange={(e) => setReplyFiles(Array.from(e.target.files || []))}
                    style={{ fontSize: '0.75rem', maxWidth: 180 }}
                  />
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      type="button"
                      onClick={handleCloseMemo}
                      style={{ background: '#f1f5f9', border: '1px solid #cbd5e1', color: '#ef4444', padding: '6px 12px', borderRadius: 6, fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer' }}
                    >
                      Close Memo
                    </button>
                    <button
                      type="submit"
                      disabled={replying}
                      style={{ background: '#6366f1', color: '#fff', border: 'none', padding: '6px 14px', borderRadius: 6, fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer', opacity: replying ? 0.7 : 1 }}
                    >
                      Send Reply
                    </button>
                  </div>
                </div>
              </form>
            )
          ) : null
        }
      />

    </div>
  )
}
