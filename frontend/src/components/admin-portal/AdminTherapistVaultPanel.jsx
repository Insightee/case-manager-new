import { useCallback, useEffect, useState } from 'react'
import { apiFetch, apiFetchBlob } from '../../lib/apiClient.js'
import { VaultDocumentPreviewModal } from '../therapist/VaultDocumentPreviewModal.jsx'
import '../therapist/therapist-vault.css'

function statusMeta(status) {
  switch (status) {
    case 'APPROVED':
      return { label: 'Approved', className: 'therapist-vault__status--approved' }
    case 'PENDING':
      return { label: 'Pending', className: 'therapist-vault__status--pending' }
    case 'REJECTED':
      return { label: 'Rejected', className: 'therapist-vault__status--rejected' }
    default:
      return { label: 'Missing', className: 'therapist-vault__status--missing' }
  }
}

function AdminVaultRow({ therapistUserId, row, canReview, onUpdated }) {
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState(null)

  const meta = statusMeta(row.status)
  const fileBase = `/api/v1/admin/therapist-profiles/${therapistUserId}/vault/documents/${row.id}/file`

  const closePreview = useCallback(() => {
    setPreview((current) => {
      if (current?.blobUrl) URL.revokeObjectURL(current.blobUrl)
      return null
    })
  }, [])

  async function openPreview() {
    if (!row.id) return
    closePreview()
    setPreview({ fileName: row.file_name, loading: true })
    try {
      const blob = await apiFetchBlob(`${fileBase}?inline=1`)
      setPreview({
        fileName: row.file_name,
        loading: false,
        blobUrl: URL.createObjectURL(blob),
        downloadPath: fileBase,
      })
    } catch (err) {
      setPreview({ fileName: row.file_name, loading: false, error: err.message || 'Could not load preview' })
    }
  }

  async function approve() {
    setBusy(true)
    setError('')
    try {
      await apiFetch(
        `/api/v1/admin/therapist-profiles/${therapistUserId}/vault/documents/${row.id}/approve`,
        { method: 'POST' },
      )
      await onUpdated()
    } catch (err) {
      setError(err.message || 'Could not approve')
    } finally {
      setBusy(false)
    }
  }

  async function reject() {
    setBusy(true)
    setError('')
    try {
      await apiFetch(
        `/api/v1/admin/therapist-profiles/${therapistUserId}/vault/documents/${row.id}/reject`,
        { method: 'POST', body: JSON.stringify({ rejection_reason: rejectReason }) },
      )
      setRejectOpen(false)
      setRejectReason('')
      await onUpdated()
    } catch (err) {
      setError(err.message || 'Could not save rejection note')
    } finally {
      setBusy(false)
    }
  }

  if (!row.id) {
    return (
      <li className="therapist-vault__row">
        <div className="therapist-vault__row-main">
          <h3 className="therapist-vault__row-title">{row.slot_label}</h3>
          <span className={`therapist-vault__status ${meta.className}`}>{meta.label}</span>
        </div>
      </li>
    )
  }

  return (
    <li className="therapist-vault__row">
      <div className="therapist-vault__row-main">
        <div className="therapist-vault__row-head">
          <h3 className="therapist-vault__row-title">{row.slot_label}</h3>
          <span className={`therapist-vault__status ${meta.className}`}>{meta.label}</span>
        </div>
        {row.file_name ? <p className="therapist-vault__file-meta">{row.file_name}</p> : null}
        {row.rejection_reason ? <p className="therapist-vault__rejection">Last note: {row.rejection_reason}</p> : null}
        {error ? <p className="therapist-vault__alert">{error}</p> : null}
        {rejectOpen ? (
          <div style={{ marginTop: 10 }}>
            <textarea
              className="admin-input"
              rows={2}
              placeholder="Tell the therapist what to fix…"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
            <div className="admin-btn-group" style={{ marginTop: 8 }}>
              <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={busy} onClick={reject}>
                Send rejection
              </button>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setRejectOpen(false)}>
                Cancel
              </button>
            </div>
          </div>
        ) : null}
      </div>
      <div className="therapist-vault__row-actions">
        <button type="button" className="therapist-vault__btn therapist-vault__btn--ghost" onClick={openPreview}>
          View
        </button>
        {canReview && row.status === 'PENDING' ? (
          <>
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={busy} onClick={approve}>
              Approve
            </button>
            <button
              type="button"
              className="admin-btn admin-btn--secondary admin-btn--sm"
              disabled={busy}
              onClick={() => setRejectOpen(true)}
            >
              Reject
            </button>
          </>
        ) : null}
      </div>
      <VaultDocumentPreviewModal
        open={Boolean(preview)}
        fileName={preview?.fileName}
        fileUrl={preview?.blobUrl}
        downloadPath={preview?.downloadPath}
        loading={preview?.loading}
        error={preview?.error}
        onClose={closePreview}
      />
    </li>
  )
}

export function AdminTherapistVaultPanel({ therapistUserId, canReview }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showHistory, setShowHistory] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const json = await apiFetch(`/api/v1/admin/therapist-profiles/${therapistUserId}/vault/documents`)
      setData(json)
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [therapistUserId])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <p className="admin-muted">Loading documents…</p>
  if (!data) return <p className="admin-muted">Could not load vault documents.</p>

  return (
    <div className="therapist-vault">
      <ul className="therapist-vault__list">
        {data.fixed_documents.map((row) => (
          <AdminVaultRow
            key={row.slot_key}
            therapistUserId={therapistUserId}
            row={row}
            canReview={canReview}
            onUpdated={load}
          />
        ))}
      </ul>
      {data.other_certifications?.length ? (
        <div className="therapist-vault__other">
          <h3 className="therapist-vault__other-title">Additional certifications</h3>
          <ul className="therapist-vault__list">
            {data.other_certifications.map((row) => (
              <AdminVaultRow
                key={row.id}
                therapistUserId={therapistUserId}
                row={row}
                canReview={canReview}
                onUpdated={load}
              />
            ))}
          </ul>
        </div>
      ) : null}
      <button
        type="button"
        className="admin-btn admin-btn--ghost admin-btn--sm"
        style={{ marginTop: 12 }}
        onClick={() => setShowHistory((v) => !v)}
      >
        {showHistory ? 'Hide upload history' : 'Show upload history'}
      </button>
      {showHistory ? (
        <div style={{ marginTop: 12, fontSize: '0.8125rem' }}>
          {Object.entries(data.history_by_slot || {}).map(([slotKey, rows]) => (
            <div key={slotKey} style={{ marginBottom: 12 }}>
              <strong>{slotKey}</strong>
              <ul>
                {rows.map((h) => (
                  <li key={h.id}>
                    v{h.version} · {h.status} · {h.file_name}
                    {h.reviewer_name ? ` · ${h.reviewer_name}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
