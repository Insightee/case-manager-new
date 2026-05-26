import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const SERVICE_LINES = [
  { value: 'shadow_support', label: 'Shadow support' },
  { value: 'homecare', label: 'Homecare' },
  { value: 'counselling', label: 'Counselling' },
  { value: 'occupational_therapy', label: 'Occupational therapy' },
]

export function TherapistLeaveBalancePanel({
  therapistUserId,
  year: yearProp,
  canEdit = false,
  onSaved,
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

  if (loading) {
    return <p style={{ fontSize: '0.875rem', color: '#94a3b8' }}>Loading leave balance…</p>
  }

  if (!balance) {
    return error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null
  }

  return (
    <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #e2e8f0' }}>
      <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem', fontWeight: 700 }}>Leave balance ({year})</h3>
      <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '0 0 12px' }}>
        Balances refresh each January. Use backfill for leave taken before the new system or when auto totals are wrong.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 12, fontSize: '0.8rem' }}>
        <div style={{ padding: 8, background: '#f8fafc', borderRadius: 8 }}>
          <div style={{ color: '#64748b' }}>Paid entitlement</div>
          <div style={{ fontWeight: 700 }}>{balance.entitlement_paid}</div>
        </div>
        <div style={{ padding: 8, background: '#f0fdf4', borderRadius: 8 }}>
          <div style={{ color: '#64748b' }}>Paid remaining</div>
          <div style={{ fontWeight: 700, color: '#15803d' }}>{balance.paid_remaining}</div>
        </div>
        <div style={{ padding: 8, background: '#f8fafc', borderRadius: 8 }}>
          <div style={{ color: '#64748b' }}>Used (system)</div>
          <div style={{ fontWeight: 600 }}>{balance.computed_paid_used} paid · {balance.computed_carry_forward_used} carry</div>
        </div>
        <div style={{ padding: 8, background: '#f8fafc', borderRadius: 8 }}>
          <div style={{ color: '#64748b' }}>HR backfill</div>
          <div style={{ fontWeight: 600 }}>{balance.backfill_paid_used} paid · {balance.backfill_carry_forward_used} carry</div>
        </div>
      </div>

      {balance.backfill_paid_used > 0 && balance.backfill_note ? (
        <p style={{ fontSize: '0.75rem', color: '#6366f1', marginBottom: 12 }}>Note: {balance.backfill_note}</p>
      ) : null}

      {canEdit ? (
        <form onSubmit={saveBackfill} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <label style={{ fontSize: '0.8rem' }}>
            Employment start date
            <input
              type="date"
              value={employmentStart}
              onChange={(e) => setEmploymentStart(e.target.value)}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '6px 8px', borderRadius: 6, border: '1px solid #d1d5db' }}
            />
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <label style={{ fontSize: '0.8rem' }}>
              Paid days (backfill)
              <input
                type="number"
                min={0}
                value={paidBackfill}
                onChange={(e) => setPaidBackfill(e.target.value)}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '6px 8px', borderRadius: 6, border: '1px solid #d1d5db' }}
              />
            </label>
            <label style={{ fontSize: '0.8rem' }}>
              Carry forward (backfill)
              <input
                type="number"
                min={0}
                value={carryBackfill}
                onChange={(e) => setCarryBackfill(e.target.value)}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '6px 8px', borderRadius: 6, border: '1px solid #d1d5db' }}
              />
            </label>
          </div>
          <label style={{ fontSize: '0.8rem' }}>
            Note {Number(paidBackfill) > 0 || Number(carryBackfill) > 0 ? '(required if backfill &gt; 0)' : ''}
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '6px 8px', borderRadius: 6, border: '1px solid #d1d5db' }}
            />
          </label>
          {error ? <p style={{ color: '#b91c1c', fontSize: '0.8rem', margin: 0 }}>{error}</p> : null}
          {success ? <p style={{ color: '#15803d', fontSize: '0.8rem', margin: 0 }}>{success}</p> : null}
          <button
            type="submit"
            disabled={saving}
            style={{ padding: '8px 14px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer', alignSelf: 'flex-start' }}
          >
            {saving ? 'Saving…' : 'Save leave settings'}
          </button>
        </form>
      ) : null}
    </div>
  )
}

export { SERVICE_LINES }
