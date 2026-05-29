import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { isLeaveBalanceUpdated, leaveBalancePaidRemainingLabel } from '../../lib/leaveBalanceDisplay.js'

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
  const [paidBackfill, setPaidBackfill] = useState(0)
  const [carryBackfill, setCarryBackfill] = useState(0)
  const [note, setNote] = useState('')
  const [employmentStart, setEmploymentStart] = useState('')

  async function loadBalance() {
    if (!therapistUserId) return
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/leave/balance/${therapistUserId}?year=${year}`)
      setBalance(data)
      setPaidBackfill(data.backfill_paid_used ?? 0)
      setCarryBackfill(data.backfill_carry_forward_used ?? 0)
      setNote(data.backfill_note || '')
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
          leave_paid_days_backfill: Number(paidBackfill) || 0,
          leave_carry_forward_days_backfill: Number(carryBackfill) || 0,
          leave_backfill_note: note || null,
          employment_start_date: employmentStart || null,
        }),
      })
      setSuccess('Leave balance settings saved.')
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
      <h3 className="therapist-leave-panel__title">Leave balance ({year})</h3>
      <p className="therapist-leave-panel__lead">
        Balances refresh each January. Use backfill for leave taken before the new system or when auto totals are wrong.
      </p>

      {!updated ? (
        <p className="therapist-leave-panel__banner">
          Add consultant start date below to calculate paid entitlement and remaining days for {year}.
        </p>
      ) : null}

      <div className="therapist-leave-panel__stats">
        <div className="therapist-leave-panel__stat">
          <div className="therapist-leave-panel__stat-label">Paid entitlement</div>
          <div
            className={`therapist-leave-panel__stat-value ${updated ? '' : 'therapist-leave-panel__stat-value--muted'}`}
          >
            {updated ? balance.entitlement_paid : pendingLabel}
          </div>
        </div>
        <div className="therapist-leave-panel__stat therapist-leave-panel__stat--highlight">
          <div className="therapist-leave-panel__stat-label">Paid remaining</div>
          <div
            className={`therapist-leave-panel__stat-value ${updated ? 'therapist-leave-panel__stat-value--ok' : 'therapist-leave-panel__stat-value--muted'}`}
          >
            {updated ? leaveBalancePaidRemainingLabel(balance) : pendingLabel}
          </div>
        </div>
        <div className="therapist-leave-panel__stat">
          <div className="therapist-leave-panel__stat-label">Used (system)</div>
          <div className={`therapist-leave-panel__stat-value ${updated ? '' : 'therapist-leave-panel__stat-value--muted'}`}>
            {updated
              ? `${balance.computed_paid_used} paid · ${balance.computed_carry_forward_used} carry`
              : pendingLabel}
          </div>
        </div>
        <div className="therapist-leave-panel__stat">
          <div className="therapist-leave-panel__stat-label">HR backfill</div>
          <div className={`therapist-leave-panel__stat-value ${updated ? '' : 'therapist-leave-panel__stat-value--muted'}`}>
            {updated
              ? `${balance.backfill_paid_used} paid · ${balance.backfill_carry_forward_used} carry`
              : pendingLabel}
          </div>
        </div>
      </div>

      {balance.backfill_paid_used > 0 && balance.backfill_note ? (
        <p className="admin-muted" style={{ fontSize: '0.75rem', margin: '0 0 12px' }}>
          Note: {balance.backfill_note}
        </p>
      ) : null}

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
          <div className="therapist-leave-panel__form-grid">
            <label className="admin-filter-field">
              <span className="admin-filter-field__label">Paid days (backfill)</span>
              <input
                type="number"
                min={0}
                className="admin-input"
                value={paidBackfill}
                onChange={(e) => setPaidBackfill(e.target.value)}
              />
            </label>
            <label className="admin-filter-field">
              <span className="admin-filter-field__label">Carry forward (backfill)</span>
              <input
                type="number"
                min={0}
                className="admin-input"
                value={carryBackfill}
                onChange={(e) => setCarryBackfill(e.target.value)}
              />
            </label>
          </div>
          <label className="admin-filter-field">
            <span className="admin-filter-field__label">
              Note {Number(paidBackfill) > 0 || Number(carryBackfill) > 0 ? '(required if backfill > 0)' : ''}
            </span>
            <textarea className="admin-input" value={note} onChange={(e) => setNote(e.target.value)} rows={2} />
          </label>
          {error ? <p className="admin-alert admin-alert--error" style={{ margin: 0 }}>{error}</p> : null}
          {success ? <p className="admin-alert admin-alert--success" style={{ margin: 0 }}>{success}</p> : null}
          <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={saving}>
            {saving ? 'Saving…' : 'Save leave settings'}
          </button>
        </form>
      ) : null}
    </div>
  )
}
