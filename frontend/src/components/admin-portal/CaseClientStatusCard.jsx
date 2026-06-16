import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import './admin-client-status.css'

const STATUS_LABELS = {
  ACTIVE: 'Active',
  PENDING_ALLOTMENT: 'Pending allotment',
  SUSPENDED: 'Suspended',
  PENDING_REPLACEMENT: 'Pending replacement',
  DEACTIVATED: 'Deactivated',
  CLOSED: 'Closed',
}

const STATUS_IMPACTS = {
  ACTIVE: 'Services, sessions, billing, and reports continue normally.',
  SUSPENDED:
    'Billing will stop from the effective date. Future scheduled sessions will be cancelled. Parent portal will show service as paused.',
  PENDING_REPLACEMENT:
    'Billing stops from the effective date. The case remains open pending therapist reassignment. No new sessions will be auto-scheduled.',
  DEACTIVATED:
    'Final billing will be calculated up to the effective date. All future sessions will be cancelled. No new sessions can be created. Records remain accessible.',
  CLOSED:
    'Case is closed. Final billing settlement applies. No new sessions can be created.',
}

// Admin-allowed transitions per status
const ALLOWED_NEXT = {
  PENDING_ALLOTMENT: ['ACTIVE'],
  ACTIVE: ['SUSPENDED', 'PENDING_REPLACEMENT', 'DEACTIVATED'],
  SUSPENDED: ['ACTIVE', 'DEACTIVATED'],
  PENDING_REPLACEMENT: ['ACTIVE', 'DEACTIVATED'],
  DEACTIVATED: [],
  CLOSED: [],
}

function StatusBadge({ status }) {
  const key = (status || 'ACTIVE').toLowerCase()
  return (
    <span className={`cs-badge cs-badge--${key}`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function ChangeStatusModal({ currentStatus, caseId, onClose, onSuccess }) {
  const allowed = ALLOWED_NEXT[currentStatus] || []
  const [newStatus, setNewStatus] = useState(allowed[0] || '')
  const [effectiveDate, setEffectiveDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [reason, setReason] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const impact = STATUS_IMPACTS[newStatus] || ''

  async function handleSubmit() {
    if (!newStatus || !effectiveDate || reason.trim().length < 5) {
      setError('Please fill in all required fields. Reason must be at least 5 characters.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/cases/${caseId}/client-status`, {
        method: 'POST',
        body: JSON.stringify({
          new_status: newStatus,
          effective_date: effectiveDate,
          reason: reason.trim(),
          internal_notes: notes.trim() || null,
        }),
      })
      onSuccess?.(result)
      onClose?.()
    } catch (err) {
      setError(err.message || 'Could not update status')
    } finally {
      setSaving(false)
    }
  }

  if (allowed.length === 0) {
    return (
      <div className="cs-modal-overlay" onClick={onClose}>
        <div className="cs-modal" onClick={(e) => e.stopPropagation()}>
          <p className="cs-modal__title">Status cannot be changed</p>
          <p style={{ fontSize: '0.875rem', color: '#64748b' }}>
            This case is in a terminal state ({STATUS_LABELS[currentStatus]}) and cannot be transitioned further.
          </p>
          <div className="cs-modal__actions">
            <button type="button" className="admin-btn admin-btn--ghost" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="cs-modal-overlay" onClick={onClose}>
      <div className="cs-modal" onClick={(e) => e.stopPropagation()}>
        <p className="cs-modal__title">Change client status</p>

        {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

        <div className="admin-form-grid" style={{ maxWidth: '100%' }}>
          <label className="admin-label" style={{ gridColumn: '1 / -1' }}>
            New status <span style={{ color: '#ef4444' }}>*</span>
            <select
              className="admin-input"
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value)}
            >
              {allowed.map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>
              ))}
            </select>
          </label>

          <label className="admin-label">
            Effective date <span style={{ color: '#ef4444' }}>*</span>
            <input
              type="date"
              className="admin-input"
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
            />
          </label>

          <label className="admin-label" style={{ gridColumn: '1 / -1' }}>
            Reason for change <span style={{ color: '#ef4444' }}>*</span>
            <input
              type="text"
              className="admin-input"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Min 5 characters — e.g. Therapist resigned, service paused pending review"
            />
          </label>

          <label className="admin-label" style={{ gridColumn: '1 / -1' }}>
            Internal notes (optional)
            <textarea
              className="admin-input"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Additional context visible to admin team only"
            />
          </label>
        </div>

        {impact ? (
          <div className="cs-modal__impact">
            <strong>Billing & service impact:</strong><br />
            {impact}
          </div>
        ) : null}

        {newStatus ? (
          <div className="cs-modal__confirm">
            You are changing this client status to <strong>{STATUS_LABELS[newStatus] || newStatus}</strong>{' '}
            effective from <strong>{effectiveDate || '—'}</strong>. This may affect services, scheduling, and billing from this date. Are you sure?
          </div>
        ) : null}

        <div className="cs-modal__actions">
          <button type="button" className="admin-btn admin-btn--ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--primary"
            onClick={handleSubmit}
            disabled={saving || !newStatus || !effectiveDate || reason.trim().length < 5}
          >
            {saving ? 'Saving…' : 'Confirm status change'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function CaseClientStatusCard({ caseId, caseRow, canEdit, onStatusChanged }) {
  const [auditData, setAuditData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [error, setError] = useState('')

  const currentStatus = caseRow?.status || 'PENDING_ALLOTMENT'

  const loadAudit = useCallback(() => {
    if (!caseId) return
    setLoading(true)
    apiFetch(`/api/v1/cases/${caseId}/client-status/audit`)
      .then(setAuditData)
      .catch((err) => setError(err.message || 'Could not load status history'))
      .finally(() => setLoading(false))
  }, [caseId])

  useEffect(() => {
    loadAudit()
  }, [loadAudit])

  // Determine ageing warning
  const today = new Date()
  const effectiveDateStr = auditData?.statusEffectiveDate || caseRow?.status_effective_date
  const ageingDays = effectiveDateStr
    ? Math.floor((today - new Date(effectiveDateStr)) / (1000 * 60 * 60 * 24))
    : null
  const showAgeingWarn =
    ['SUSPENDED', 'PENDING_REPLACEMENT'].includes(currentStatus) &&
    ageingDays !== null &&
    ageingDays > 7

  function handleSuccess(result) {
    loadAudit()
    if (onStatusChanged) {
      onStatusChanged(result.case)
    }
  }

  return (
    <div className="case-status-card">
      <div className="case-status-card__header">
        <div className="case-status-card__left">
          <StatusBadge status={currentStatus} />
          {effectiveDateStr ? (
            <p className="case-status-card__meta">
              Effective: {effectiveDateStr}
              {caseRow?.status_reason ? ` · ${caseRow.status_reason}` : ''}
            </p>
          ) : null}
        </div>
        {canEdit ? (
          <button
            type="button"
            className="admin-btn admin-btn--secondary admin-btn--sm"
            onClick={() => setShowModal(true)}
          >
            Change Status
          </button>
        ) : null}
      </div>

      {showAgeingWarn ? (
        <div className="cs-ageing-warn">
          ⚠️ {STATUS_LABELS[currentStatus]} for <strong>{ageingDays} days</strong> — action may be needed
        </div>
      ) : null}

      {error ? <p className="admin-alert admin-alert--error" style={{ marginTop: 8 }}>{error}</p> : null}

      <div className="cs-audit">
        <p className="cs-audit__title">Status history</p>
        {loading ? (
          <p className="admin-muted" style={{ fontSize: '0.825rem' }}>Loading history…</p>
        ) : !auditData?.audit?.length ? (
          <p className="admin-muted" style={{ fontSize: '0.825rem' }}>No status changes recorded yet.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="cs-audit__table">
              <thead>
                <tr>
                  <th>Change</th>
                  <th>Effective</th>
                  <th>Reason</th>
                  <th>Changed by</th>
                  <th>Changed at</th>
                  <th>Ageing</th>
                </tr>
              </thead>
              <tbody>
                {auditData.audit.map((row) => (
                  <tr
                    key={row.id}
                    className={row.ageingWarning ? 'cs-audit__row--warn' : ''}
                  >
                    <td>
                      <StatusBadge status={row.previousStatus} />
                      <span className="cs-audit__arrow">→</span>
                      <StatusBadge status={row.newStatus} />
                    </td>
                    <td>{row.effectiveDate}</td>
                    <td>
                      <div>{row.reason}</div>
                      {row.internalNotes ? (
                        <div style={{ fontStyle: 'italic', color: '#64748b', fontSize: '0.75rem', marginTop: 2 }}>
                          Notes: {row.internalNotes}
                        </div>
                      ) : null}
                    </td>
                    <td>{row.changedBy || '—'}</td>
                    <td>{row.changedAt ? new Date(row.changedAt).toLocaleString() : '—'}</td>
                    <td>
                      {row.ageingDays !== null ? (
                        <span className="cs-audit__ageing">
                          ⏱️ {row.ageingDays}d
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal ? (
        <ChangeStatusModal
          currentStatus={currentStatus}
          caseId={caseId}
          onClose={() => setShowModal(false)}
          onSuccess={handleSuccess}
        />
      ) : null}
    </div>
  )
}
