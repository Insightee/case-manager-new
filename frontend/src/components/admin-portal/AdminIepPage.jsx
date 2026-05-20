import { useEffect, useState } from 'react'
import { apiFetch, apiUpload, getTokens } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState, StatusBadge } from './ui/index.js'

const API_URL = import.meta.env.VITE_API_URL || ''

async function downloadAttachment(id, fileName) {
  const { access } = getTokens()
  const res = await fetch(`${API_URL}/api/v1/attachments/${id}/download`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  })
  if (!res.ok) throw new Error('Download failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName || 'iep-document'
  a.click()
  URL.revokeObjectURL(url)
}

export function AdminIepPage() {
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [files, setFiles] = useState([])
  const [version, setVersion] = useState('v1')
  const [loadingFiles, setLoadingFiles] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    apiFetch('/api/v1/cases?page_size=100')
      .then((d) => setCases(unwrapList(d)))
      .catch(() => setCases([]))
  }, [])

  const selectedCase = cases.find((c) => String(c.id) === String(caseId))

  async function loadFiles(id) {
    if (!id) return
    setLoadingFiles(true)
    try {
      setFiles(await apiFetch(`/api/v1/attachments?case_id=${id}`))
    } catch {
      setFiles([])
    } finally {
      setLoadingFiles(false)
    }
  }

  async function upload(e) {
    e.preventDefault()
    setMessage('')
    const file = e.target.file.files[0]
    if (!file || !caseId) return
    const fd = new FormData()
    fd.append('case_id', caseId)
    fd.append('entity_type', 'iep')
    fd.append('version', version)
    fd.append('visibility_status', 'INTERNAL_ONLY')
    fd.append('file', file)
    await apiUpload('/api/v1/attachments', fd)
    loadFiles(caseId)
    setMessage('IEP uploaded. Use Share with parent when ready.')
  }

  async function shareWithParent(attachmentId) {
    setMessage('')
    try {
      await apiFetch(`/api/v1/attachments/${attachmentId}`, {
        method: 'PATCH',
        body: JSON.stringify({ visibility_status: 'APPROVED_FOR_PARENT' }),
      })
      setMessage('Document shared with parent for acknowledgement.')
      loadFiles(caseId)
    } catch (err) {
      setMessage(err.message || 'Could not update visibility')
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader eyebrow="Documentation" title="IEP management" subtitle="Upload, download, and share IEP documents per case." />

      {message ? <p style={{ marginBottom: 16, color: '#047857' }}>{message}</p> : null}

      <div className="admin-layout admin-layout--stack" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <AdminPanel title="Select case">
          <div className="admin-form-grid">
            <label>
              Case
              <select
                value={caseId}
                onChange={(e) => {
                  setCaseId(e.target.value)
                  loadFiles(e.target.value)
                }}
              >
                <option value="">Choose a case…</option>
                {cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_code} — {c.child_name}
                  </option>
                ))}
              </select>
            </label>
            {selectedCase ? (
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', margin: 0 }}>
                {selectedCase.service_type} · {selectedCase.product_module}
              </p>
            ) : null}
          </div>
        </AdminPanel>

        <AdminPanel title="Upload document">
          <form onSubmit={upload} className="admin-form-grid">
            <label>
              Version
              <input value={version} onChange={(e) => setVersion(e.target.value)} />
            </label>
            <label>
              PDF file
              <input type="file" name="file" accept=".pdf,.txt" disabled={!caseId} />
            </label>
            <button type="submit" className="admin-btn admin-btn--primary" disabled={!caseId}>
              Upload IEP
            </button>
          </form>
        </AdminPanel>
      </div>

      <AdminPanel title={selectedCase ? `Files — ${selectedCase.case_code}` : 'Case files'}>
        {!caseId ? (
          <AdminEmptyState title="Select a case" description="Choose a case to view and manage IEP attachments." />
        ) : loadingFiles ? (
          <div className="admin-skeleton" />
        ) : files.length === 0 ? (
          <AdminEmptyState title="No attachments" description="Upload a PDF to add the first IEP document." />
        ) : (
          <ul className="admin-queue">
            {files.map((f) => (
              <li key={f.id} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">{f.file_name}</p>
                  <p className="admin-queue__meta">
                    {f.version} · {f.entity_type}
                  </p>
                </div>
                <div className="admin-btn-group">
                  <StatusBadge status={f.visibility_status} />
                  <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => downloadAttachment(f.id, f.file_name)}>
                    Download
                  </button>
                  {f.visibility_status !== 'APPROVED_FOR_PARENT' && f.visibility_status !== 'SHARED_WITH_PARENT' ? (
                    <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => shareWithParent(f.id)}>
                      Share with parent
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </AdminPanel>
    </div>
  )
}
