import { useState } from 'react'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'

const BULK_YEAR = 2026

const TEMPLATE_CSV = `external_employee_id,start_date
EMP-101,2025-11-01`

export function BulkLeaveUpload({ onApplied }) {
  const [csvText, setCsvText] = useState('')
  const [preview, setPreview] = useState(null)
  const [phase, setPhase] = useState('edit')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function runPreview() {
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const data = await apiFetch('/api/v1/hr/leave/bulk/preview', {
        method: 'POST',
        body: JSON.stringify({ csv_text: csvText, year: BULK_YEAR }),
      })
      setPreview(data)
      setPhase('preview')
    } catch (err) {
      setPreview(null)
      setPhase('edit')
      setError(err.message || 'Could not preview CSV')
    } finally {
      setLoading(false)
    }
  }

  async function runApply() {
    if (!preview?.ok_rows) {
      setError('Fix all row errors before applying.')
      return
    }
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const data = await apiFetch('/api/v1/hr/leave/bulk/apply', {
        method: 'POST',
        body: JSON.stringify({ csv_text: csvText, year: BULK_YEAR }),
      })
      setSuccess(`Updated start dates for ${data.updated} therapist${data.updated === 1 ? '' : 's'} (${BULK_YEAR} credits).`)
      setPhase('edit')
      setPreview(null)
      onApplied?.()
    } catch (err) {
      setError(err.message || 'Could not apply bulk import')
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setPhase('edit')
    setPreview(null)
    setError('')
    setSuccess('')
  }

  return (
    <section className="leave-mgmt-manual__panel leave-mgmt-manual__panel--wide leave-mgmt-bulk">
      <div className="leave-mgmt-bulk__header">
        <div>
          <h3 className="leave-mgmt-manual__panel-title">Bulk start date upload ({BULK_YEAR})</h3>
          <p className="admin-muted leave-mgmt-manual__hint" style={{ margin: '4px 0 0' }}>
            CSV columns: <code>external_employee_id</code>, <code>start_date</code> (YYYY-MM-DD recommended).
            Updates consultant start dates and recalculates {BULK_YEAR} leave credits. Leave history rows are not changed.
          </p>
        </div>
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          onClick={() =>
            apiDownload('/api/v1/hr/leave/bulk/template.csv', 'leave_bulk_import_2026_template.csv').catch(
              (err) => setError(err.message || 'Could not download template'),
            )
          }
        >
          Download template
        </button>
      </div>

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      {phase === 'edit' ? (
        <>
          <label className="admin-filter-field">
            <span className="admin-filter-field__label">Paste CSV</span>
            <textarea
              className="admin-input"
              rows={6}
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              placeholder={TEMPLATE_CSV}
              disabled={loading}
            />
          </label>
          <div className="leave-mgmt-bulk__actions">
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              disabled={loading || !csvText.trim()}
              onClick={runPreview}
            >
              {loading ? 'Previewing…' : 'Preview'}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="admin-muted" style={{ fontSize: '0.875rem', margin: '0 0 8px' }}>
            {preview?.ok_rows ?? 0} ready · {preview?.error_rows ?? 0} error
            {(preview?.error_rows ?? 0) > 0 ? ' — fix errors before applying' : ''}
          </p>
          <div className="admin-table-wrap">
            <table className="admin-table admin-table--compact">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Employee ID</th>
                  <th>Name</th>
                  <th>Start</th>
                  <th>Credits</th>
                  <th>Paid (records)</th>
                  <th>Credit left</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(preview?.rows || []).map((row) => (
                  <tr key={`${row.line_number}-${row.external_employee_id}`}>
                    <td>{row.line_number}</td>
                    <td>{row.external_employee_id}</td>
                    <td>{row.therapist_name || '—'}</td>
                    <td>{row.start_date || '—'}</td>
                    <td>{row.credits_earned ?? '—'}</td>
                    <td>{row.paid_used ?? '—'}</td>
                    <td>{row.leave_credit_pending ?? '—'}</td>
                    <td>
                      {row.status === 'ok' ? (
                        <span className="admin-chip admin-chip--sm">Ready</span>
                      ) : (
                        <span className="admin-chip admin-chip--sm admin-chip--danger" title={row.error}>
                          Error
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(preview?.rows || []).some((r) => r.error) ? (
            <ul className="leave-mgmt-bulk__errors">
              {preview.rows
                .filter((r) => r.error)
                .map((r) => (
                  <li key={r.line_number}>
                    Line {r.line_number}: {r.error}
                  </li>
                ))}
            </ul>
          ) : null}
          <div className="leave-mgmt-bulk__actions">
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={loading} onClick={reset}>
              Back
            </button>
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              disabled={loading || (preview?.error_rows ?? 0) > 0}
              onClick={runApply}
            >
              {loading ? 'Applying…' : `Apply start dates for ${BULK_YEAR}`}
            </button>
          </div>
        </>
      )}
    </section>
  )
}
