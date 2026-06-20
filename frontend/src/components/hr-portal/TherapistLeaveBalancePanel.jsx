import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { isLeaveBalanceUpdated, leaveCreditPendingLabel, leaveUsedSummaryLabel } from '../../lib/leaveBalanceDisplay.js'

export function TherapistLeaveBalancePanel({
  therapistUserId,
  year: yearProp,
  canEdit = false,
  onSaved,
  className = '',
}) {
  const year = yearProp || new Date().getFullYear()
  const [balance, setBalance] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [employmentStart, setEmploymentStart] = useState('')

  async function loadBalance() {
    if (!therapistUserId) return
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/leave/balance/${therapistUserId}?year=${year}`)
      setBalance(data)
      setEmploymentStart(data.employment_start_date || '')
    } catch (err) {
      setBalance(null)
      setError(err.message || 'Could not load leave balance')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBalance()
  }, [therapistUserId, year])

  async function saveBackfill(e) {
    e.preventDefault()
    if (!canEdit) return
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/hr/therapists/${therapistUserId}/leave-backfill`, {
        method: 'PATCH',
        body: JSON.stringify({
          year,
          employment_start_date: employmentStart || null,
        }),
      })
      setSuccess('Leave credit settings saved.')
      await loadBalance()
      onSaved?.()
    } catch (err) {
      setError(err.message || 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  const panelClass = ['therapist-leave-panel', className].filter(Boolean).join(' ')

  if (loading) {
    return (
      <div className={panelClass}>
        <p className="admin-muted" style={{ margin: 0, fontSize: '0.875rem' }}>
          Loading leave balance…
        </p>
      </div>
    )
  }

  if (!balance) {
    return error ? (
      <div className={panelClass}>
        <p className="admin-alert admin-alert--error" style={{ margin: 0 }}>
          {error}
        </p>
      </div>
    ) : null
  }

  const updated = isLeaveBalanceUpdated(balance)
  const pendingLabel = updated ? null : 'Pending setup'

  return (
    <div className={panelClass}>
      <h3 className="therapist-leave-panel__title">Leave credit ({year})</h3>
      <p className="therapist-leave-panel__lead">
        One credit accrues each calendar month from the consultant start date. Credits expire on 31 December.
      </p>

      <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16, fontSize: '0.85rem', color: '#4b5563', flexWrap: 'wrap' }}>
        <div>
          <span style={{ fontWeight: 600 }}>Start date:</span>{' '}
          {balance.employment_start_date ? (
            <span style={{ color: '#111827', fontWeight: 500 }}>
              {new Date(balance.employment_start_date).toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            </span>
          ) : (
            <span style={{ color: '#ef4444', fontWeight: 600 }}>Not set</span>
          )}
          {balance.employment_start_date && balance.profile_status && balance.profile_status !== 'APPROVED' ? (
            <span
              style={{
                marginLeft: 8,
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '2px 6px',
                borderRadius: 4,
                background: balance.profile_status === 'PENDING' ? '#fef3c7' : '#f4f4f5',
                color: balance.profile_status === 'PENDING' ? '#b45309' : '#52525b',
              }}
            >
              {balance.profile_status === 'PENDING' ? 'Pending approval' : 'Draft'}
            </span>
          ) : null}
        </div>
        {balance.employment_start_date ? (
          <div>
            <span style={{ fontWeight: 600 }}>Credits earned:</span>{' '}
            <span style={{ color: '#111827', fontWeight: 500 }}>{balance.credits_earned ?? 0}</span>
          </div>
        ) : null}
      </div>

      {!updated ? (
        <p className="therapist-leave-panel__banner">
          Add consultant start date below to calculate leave credits for {year}.
        </p>
      ) : null}

      <div className="therapist-leave-panel__stats">
        <div className="therapist-leave-panel__stat therapist-leave-panel__stat--highlight">
          <div className="therapist-leave-panel__stat-label">Leave credit</div>
          <div
            className={`therapist-leave-panel__stat-value ${updated ? 'therapist-leave-panel__stat-value--ok' : 'therapist-leave-panel__stat-value--muted'}`}
          >
            {updated ? leaveCreditPendingLabel(balance) : pendingLabel}
          </div>
        </div>
        <div className="therapist-leave-panel__stat">
          <div className="therapist-leave-panel__stat-label">Paid leaves taken</div>
          <div className={`therapist-leave-panel__stat-value ${updated ? '' : 'therapist-leave-panel__stat-value--muted'}`}>
            {updated ? balance.paid_leaves_taken ?? balance.computed_paid_used ?? 0 : pendingLabel}
          </div>
        </div>
        <div className="therapist-leave-panel__stat">
          <div className="therapist-leave-panel__stat-label">Unpaid leaves taken</div>
          <div className={`therapist-leave-panel__stat-value ${updated ? '' : 'therapist-leave-panel__stat-value--muted'}`}>
            {updated ? balance.unpaid_leaves_taken ?? balance.computed_unpaid_days ?? 0 : pendingLabel}
          </div>
        </div>
        <div className="therapist-leave-panel__stat">
          <div className="therapist-leave-panel__stat-label">Used summary</div>
          <div className={`therapist-leave-panel__stat-value ${updated ? '' : 'therapist-leave-panel__stat-value--muted'}`}>
            {updated ? leaveUsedSummaryLabel(balance) : pendingLabel}
          </div>
        </div>
      </div>

      {canEdit ? (
        <form onSubmit={saveBackfill} className="therapist-leave-panel__form">
          <label className="admin-filter-field">
            <span className="admin-filter-field__label">Consultant start date</span>
            <input
              type="date"
              className="admin-input"
              value={employmentStart}
              onChange={(e) => setEmploymentStart(e.target.value)}
            />
          </label>
          {error ? <p className="admin-alert admin-alert--error" style={{ margin: 0 }}>{error}</p> : null}
          {success ? <p className="admin-alert admin-alert--success" style={{ margin: 0 }}>{success}</p> : null}
          <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={saving}>
            {saving ? 'Saving…' : 'Save start date'}
          </button>
        </form>
      ) : null}
    </div>
  )
}
