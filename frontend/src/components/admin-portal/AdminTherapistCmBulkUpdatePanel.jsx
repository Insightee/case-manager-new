import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { parseTherapistCmBulkCsv } from '../../lib/therapistCmBulkCsv.js'
import { AdminPanel } from './ui/index.js'

function statusTone(status) {
  if (status === 'updated' || status === 'will_update') return 'success'
  if (status === 'unchanged') return 'neutral'
  return 'error'
}

const PASTE_PLACEHOLDER = `Therapist ID,Email,Primary CM,Case Manager Email
T-101,therapist@example.com,Priya Sharma,casemanager@example.com
T-102,therapist2@example.com,Another CM,another.cm@example.com`

export function AdminTherapistCmBulkUpdatePanel({ onSuccess, onError, onReload }) {
  const [open, setOpen] = useState(false)
  const [phase, setPhase] = useState('upload')
  const [preview, setPreview] = useState(null)
  const [rows, setRows] = useState([])
  const [pasteText, setPasteText] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function resetUpload() {
    setPhase('upload')
    setPreview(null)
    setRows([])
    setPasteText('')
  }

  function close() {
    setOpen(false)
    resetUpload()
  }

  async function runRequest(uploadRows, apply) {
    return apiFetch('/api/v1/admin/therapists/bulk-update-primary-cm', {
      method: 'POST',
      body: JSON.stringify({ rows: uploadRows, apply }),
    })
  }

  async function previewFromText(text) {
    const parsed = parseTherapistCmBulkCsv(text)
    if (!parsed.length) {
      onError?.('No valid rows found. Use columns: Therapist ID, Email, Primary CM, Case Manager Email.')
      return
    }
    const missingCm = parsed.filter((row) => !row.case_manager_email)
    if (missingCm.length) {
      onError?.('Every row needs a Case Manager Email.')
      return
    }
    onError?.('')
    setSubmitting(true)
    try {
      const result = await runRequest(parsed, false)
      setRows(parsed)
      setPreview(result)
      setPhase('preview')
    } catch (err) {
      onError?.(err.message || 'Could not preview case manager updates')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleFileChange(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    try {
      const text = await file.text()
      setPasteText(text)
      await previewFromText(text)
    } catch (err) {
      onError?.(err.message || 'Could not read CSV file')
    }
  }

  async function handlePastePreview() {
    if (!pasteText.trim()) {
      onError?.('Paste CSV rows or upload a file first.')
      return
    }
    await previewFromText(pasteText)
  }

  async function confirmApply() {
    if (!rows.length) return
    setSubmitting(true)
    onError?.('')
    try {
      const result = await runRequest(rows, true)
      setPreview(result)
      setPhase('done')
      const { updated = 0, unchanged = 0, failed = 0 } = result.summary || {}
      onSuccess?.(`Case managers updated: ${updated} changed, ${unchanged} unchanged, ${failed} failed.`)
      onReload?.()
    } catch (err) {
      onError?.(err.message || 'Could not apply case manager updates')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <button
        type="button"
        className="admin-btn admin-btn--ghost admin-btn--sm"
        onClick={() => {
          resetUpload()
          setOpen(true)
        }}
      >
        Update case managers
      </button>

      {open ? (
        <div className="admin-drawer-backdrop" role="presentation" onClick={close}>
          <div
            className="admin-drawer admin-drawer--wide"
            role="dialog"
            aria-labelledby="therapist-cm-bulk-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="admin-drawer__header">
              <h2 id="therapist-cm-bulk-title">Update therapist case managers</h2>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={close} aria-label="Close">
                Close
              </button>
            </header>

            <div className="admin-drawer__body">
              <p className="admin-muted" style={{ marginTop: 0 }}>
                Upload a CSV or paste spreadsheet rows with columns{' '}
                <code>Therapist ID, Email, Primary CM, Case Manager Email</code>. Only rows with a different case
                manager are updated. Active cases for each therapist are updated too.
              </p>

              {phase === 'upload' ? (
                <>
                  <label className="admin-input" style={{ display: 'block', marginBottom: 16 }}>
                    <span className="admin-filter-field__label">CSV file</span>
                    <input
                      type="file"
                      accept=".csv,text/csv"
                      className="admin-input"
                      disabled={submitting}
                      onChange={handleFileChange}
                    />
                  </label>
                  <label className="admin-input" style={{ display: 'block' }}>
                    <span className="admin-filter-field__label">Or paste rows</span>
                    <textarea
                      className="admin-input"
                      rows={10}
                      placeholder={PASTE_PLACEHOLDER}
                      value={pasteText}
                      disabled={submitting}
                      onChange={(event) => setPasteText(event.target.value)}
                      style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.85rem' }}
                    />
                  </label>
                  <div className="admin-btn-group" style={{ marginTop: 12 }}>
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary admin-btn--sm"
                      disabled={submitting || !pasteText.trim()}
                      onClick={handlePastePreview}
                    >
                      {submitting ? 'Previewing…' : 'Preview rows'}
                    </button>
                  </div>
                </>
              ) : null}

              {preview ? (
                <AdminPanel
                  title={
                    phase === 'done'
                      ? 'Update results'
                      : `Preview (${preview.summary?.will_update ?? 0} to update, ${preview.summary?.unchanged ?? 0} unchanged, ${preview.summary?.failed ?? 0} failed)`
                  }
                  padded={false}
                >
                  <div className="admin-panel__body">
                    <div className="admin-table-wrap">
                      <table className="admin-table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Therapist</th>
                            <th>Case manager</th>
                            <th>Status</th>
                            <th>Details</th>
                          </tr>
                        </thead>
                        <tbody>
                          {preview.results?.map((row) => (
                            <tr key={row.row_index}>
                              <td>{row.row_index}</td>
                              <td>
                                {row.therapist_email || '—'}
                                {row.therapist_id ? (
                                  <>
                                    <br />
                                    <span className="admin-muted">ID {row.therapist_id}</span>
                                  </>
                                ) : null}
                              </td>
                              <td>
                                {row.old_cm_email || '—'} → {row.new_cm_email || row.case_manager_email || '—'}
                              </td>
                              <td>
                                <span className={`admin-badge admin-badge--${statusTone(row.status)}`}>{row.status}</span>
                              </td>
                              <td>
                                {row.message || '—'}
                                {row.warning ? (
                                  <span className="admin-muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                                    Warning: {row.warning}
                                  </span>
                                ) : null}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </AdminPanel>
              ) : null}

              {phase === 'preview' ? (
                <div className="admin-btn-group" style={{ marginTop: 16 }}>
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary admin-btn--sm"
                    disabled={submitting || !(preview?.summary?.will_update > 0)}
                    onClick={confirmApply}
                  >
                    {submitting ? 'Applying…' : 'Apply updates'}
                  </button>
                  <button
                    type="button"
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                    disabled={submitting}
                    onClick={resetUpload}
                  >
                    Edit data
                  </button>
                </div>
              ) : null}

              {phase === 'done' ? (
                <div className="admin-btn-group" style={{ marginTop: 16 }}>
                  <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={close}>
                    Close
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
