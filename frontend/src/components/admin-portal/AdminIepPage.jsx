import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, apiUpload, getTokens } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import {
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  AdminSearchInput,
} from './ui/index.js'
import './admin-iep-dashboard.css'

const API_URL = import.meta.env.VITE_API_URL || ''

const STATUS_FILTERS = [
  { id: 'ALL', label: 'All' },
  { id: 'AWAITING_ACK', label: 'Awaiting parent ack' },
  { id: 'MISSING', label: 'No IEP uploaded' },
  { id: 'INTERNAL_ONLY', label: 'Draft / internal' },
  { id: 'ACKNOWLEDGED', label: 'Acknowledged' },
]

const STATUS_LABELS = {
  MISSING: 'No IEP',
  INTERNAL_ONLY: 'Internal draft',
  AWAITING_ACK: 'Awaiting ack',
  ACKNOWLEDGED: 'Acknowledged',
}

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

function IepStatusPill({ status }) {
  return <span className={`admin-iep-status admin-iep-status--${status}`}>{STATUS_LABELS[status] || status}</span>
}

function AdminIepUploadPanel({ onUploaded }) {
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
    setMessage('IEP uploaded. Share with parent when ready.')
    onUploaded?.()
  }

  async function shareWithParent(attachmentId) {
    setMessage('')
    try {
      await apiFetch(`/api/v1/attachments/${attachmentId}`, {
        method: 'PATCH',
        body: JSON.stringify({ visibility_status: 'APPROVED_FOR_PARENT' }),
      })
      setMessage('Shared with parent — awaiting acknowledgement.')
      loadFiles(caseId)
      onUploaded?.()
    } catch (err) {
      setMessage(err.message || 'Could not update visibility')
    }
  }

  return (
    <div className="admin-layout admin-layout--stack" style={{ gridTemplateColumns: '1fr 1fr' }}>
      <AdminPanel title="Select case">
        <div className="admin-form-grid">
          <label>
            Case
            <select
              className="admin-input"
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
        </div>
      </AdminPanel>

      <AdminPanel title="Upload document">
        <form onSubmit={upload} className="admin-form-grid">
          <label>
            Version
            <input className="admin-input" value={version} onChange={(e) => setVersion(e.target.value)} />
          </label>
          <label>
            PDF file
            <input type="file" name="file" accept=".pdf,.txt" className="admin-input" disabled={!caseId} />
          </label>
          <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={!caseId}>
            Upload IEP
          </button>
        </form>
        {message ? <p className="admin-alert admin-alert--success" style={{ marginTop: 12 }}>{message}</p> : null}
      </AdminPanel>

      <div style={{ gridColumn: '1 / -1' }}>
      <AdminPanel title={selectedCase ? `Files — ${selectedCase.case_code}` : 'Case files'}>
        {!caseId ? (
          <AdminEmptyState title="Select a case" description="Choose a case to manage versions." />
        ) : loadingFiles ? (
          <div className="admin-skeleton" />
        ) : files.filter((f) => f.entity_type === 'iep').length === 0 ? (
          <AdminEmptyState title="No IEP files" description="Upload a document above." />
        ) : (
          <ul className="admin-queue">
            {files
              .filter((f) => f.entity_type === 'iep' || !f.entity_type)
              .map((f) => (
                <li key={f.id} className="admin-queue__item">
                  <div>
                    <p className="admin-queue__title">{f.file_name}</p>
                    <p className="admin-queue__meta">{f.version}</p>
                  </div>
                  <div className="admin-btn-group">
                    <IepStatusPill
                      status={
                        f.visibility_status === 'SHARED_WITH_PARENT'
                          ? 'ACKNOWLEDGED'
                          : f.visibility_status === 'APPROVED_FOR_PARENT'
                            ? 'AWAITING_ACK'
                            : 'INTERNAL_ONLY'
                      }
                    />
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      onClick={() => downloadAttachment(f.id, f.file_name)}
                    >
                      Download
                    </button>
                    {f.visibility_status === 'INTERNAL_ONLY' ? (
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
    </div>
  )
}

export function AdminIepPage() {
  const [tab, setTab] = useState('dashboard')
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [moduleFilter, setModuleFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [includeClosed, setIncludeClosed] = useState(false)
  const [actingId, setActingId] = useState(null)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const p = new URLSearchParams()
      if (statusFilter !== 'ALL') p.set('status', statusFilter)
      if (moduleFilter !== 'all') p.set('product_module', moduleFilter)
      if (search.trim()) p.set('search', search.trim())
      if (includeClosed) p.set('include_closed', 'true')
      const data = await apiFetch(`/api/v1/admin/iep/dashboard?${p}`)
      setDashboard(data)
    } catch (err) {
      setError(err.message || 'Could not load IEP dashboard')
      setDashboard(null)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, moduleFilter, search, includeClosed])

  useEffect(() => {
    if (tab === 'dashboard') loadDashboard()
  }, [tab, loadDashboard])

  const summary = dashboard?.summary

  const kpiCards = useMemo(
    () => [
      { id: 'ALL', label: 'Active cases', value: summary?.total_cases, tone: '' },
      { id: 'AWAITING_ACK', label: 'Awaiting ack', value: summary?.awaiting_ack, tone: 'awaiting' },
      { id: 'MISSING', label: 'No IEP', value: summary?.missing, tone: 'missing' },
      { id: 'INTERNAL_ONLY', label: 'Internal draft', value: summary?.internal_only, tone: '' },
      { id: 'ACKNOWLEDGED', label: 'Acknowledged', value: summary?.acknowledged, tone: 'ack' },
    ],
    [summary],
  )

  async function shareFromRow(row) {
    if (!row.attachment_id) return
    setActingId(row.attachment_id)
    setMessage('')
    try {
      await apiFetch(`/api/v1/attachments/${row.attachment_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ visibility_status: 'APPROVED_FOR_PARENT' }),
      })
      setMessage(`Shared IEP for ${row.case_code} with parent.`)
      loadDashboard()
    } catch (err) {
      setMessage(err.message || 'Share failed')
    } finally {
      setActingId(null)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Documentation"
        title="IEP management"
        subtitle="Org-wide status for uploads, parent sharing, and acknowledgements."
      />

      <nav style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          className={`admin-btn admin-btn--sm ${tab === 'dashboard' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
          onClick={() => setTab('dashboard')}
        >
          Status dashboard
        </button>
        <button
          type="button"
          className={`admin-btn admin-btn--sm ${tab === 'upload' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
          onClick={() => setTab('upload')}
        >
          Upload & versions
        </button>
        <Link to="/admin/cases" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginLeft: 'auto' }}>
          Case pipeline
        </Link>
      </nav>

      {message ? <p className="admin-alert admin-alert--success">{message}</p> : null}
      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      {tab === 'dashboard' ? (
        <>
          <section className="admin-iep-dash__kpis" aria-label="IEP summary">
            {kpiCards.map((k) => (
              <button
                key={k.id}
                type="button"
                className={`admin-iep-dash__kpi admin-iep-dash__kpi--${k.tone} ${statusFilter === k.id ? 'is-active' : ''}`}
                onClick={() => setStatusFilter(k.id)}
              >
                <p className="admin-iep-dash__kpi-label">{k.label}</p>
                <p className="admin-iep-dash__kpi-value">{k.value ?? '—'}</p>
              </button>
            ))}
          </section>

          <AdminPanel title={`Cases (${dashboard?.rows?.length ?? 0})`} padded={false}>
            <div className="admin-panel__body">
              <AdminToolbar>
                <AdminSearchInput
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search case, child, service…"
                />
                <select
                  className="admin-input"
                  style={{ width: 'auto', minWidth: 160 }}
                  value={moduleFilter}
                  onChange={(e) => setModuleFilter(e.target.value)}
                >
                  <option value="all">All modules</option>
                  <option value="homecare">Homecare</option>
                  <option value="shadow_support">Shadow support</option>
                </select>
                <select
                  className="admin-input"
                  style={{ width: 'auto', minWidth: 180 }}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  {STATUS_FILTERS.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8125rem', color: '#64748b' }}>
                  <input type="checkbox" checked={includeClosed} onChange={(e) => setIncludeClosed(e.target.checked)} />
                  Include closed
                </label>
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={loadDashboard}>
                  Refresh
                </button>
              </AdminToolbar>

              {loading ? (
                <div className="admin-skeleton" style={{ margin: '0 16px 16px' }} />
              ) : !dashboard?.rows?.length ? (
                <AdminEmptyState title="No cases match" description="Try another filter or upload an IEP from the Upload tab." />
              ) : (
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Case</th>
                        <th>Child</th>
                        <th>Module</th>
                        <th>IEP status</th>
                        <th>Document</th>
                        <th>Parents</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboard.rows.map((row) => (
                        <tr key={row.case_id}>
                          <td>
                            <Link to={`/admin/cases/${row.case_id}`} className="admin-table__primary">
                              {row.case_code}
                            </Link>
                            <span className="admin-table__meta">{row.case_status}</span>
                          </td>
                          <td>{row.child_name || '—'}</td>
                          <td>
                            <span className="admin-chip">{row.product_module}</span>
                          </td>
                          <td>
                            <IepStatusPill status={row.iep_status} />
                          </td>
                          <td>
                            {row.file_name ? (
                              <>
                                <span>{row.file_name}</span>
                                {row.version ? (
                                  <span className="admin-table__meta">{row.version}</span>
                                ) : null}
                              </>
                            ) : (
                              <span className="admin-muted">—</span>
                            )}
                          </td>
                          <td>
                            {row.parent_contacts?.length ? (
                              <span className="admin-table__meta">{row.parent_contacts.join('; ')}</span>
                            ) : (
                              <span className="admin-muted">No parent linked</span>
                            )}
                          </td>
                          <td>
                            <div className="admin-btn-group">
                              {row.attachment_id ? (
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--ghost admin-btn--sm"
                                  onClick={() => downloadAttachment(row.attachment_id, row.file_name)}
                                >
                                  Download
                                </button>
                              ) : null}
                              {row.iep_status === 'INTERNAL_ONLY' && row.attachment_id ? (
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--primary admin-btn--sm"
                                  disabled={actingId === row.attachment_id}
                                  onClick={() => shareFromRow(row)}
                                >
                                  Share with parent
                                </button>
                              ) : null}
                              {row.iep_status === 'MISSING' ? (
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--secondary admin-btn--sm"
                                  onClick={() => {
                                    setTab('upload')
                                  }}
                                >
                                  Upload
                                </button>
                              ) : null}
                              <Link to={`/admin/cases/${row.case_id}`} className="admin-btn admin-btn--ghost admin-btn--sm">
                                Case
                              </Link>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </AdminPanel>
        </>
      ) : (
        <AdminIepUploadPanel onUploaded={loadDashboard} />
      )}
    </div>
  )
}
