import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminTherapistPicker } from './AdminTherapistPicker.jsx'
import { WEEKDAY_KEYS, WEEKDAY_LABELS } from '../scheduling/slotCalendarUtils.js'
import { QuickRecurringModal } from '../scheduling/QuickRecurringModal.jsx'

export function AdminAssignSchedulePanel({ caseItem, assignments, onDone }) {
  const [therapistId, setTherapistId] = useState('')
  const [quickOpen, setQuickOpen] = useState(false)
  const [weekdays, setWeekdays] = useState(['mon', 'wed', 'fri'])
  const [startTime, setStartTime] = useState('16:00')
  const [endTime, setEndTime] = useState('17:00')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [step, setStep] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    const active = (assignments || []).find((a) => a.status === 'ACTIVE')
    if (active) setTherapistId(String(active.therapist_user_id))
    const today = new Date()
    const end = new Date(today)
    end.setMonth(end.getMonth() + 1)
    setStartDate(today.toISOString().slice(0, 10))
    setEndDate(end.toISOString().slice(0, 10))
  }, [assignments])

  function toggleDay(key) {
    setWeekdays((prev) => (prev.includes(key) ? prev.filter((d) => d !== key) : [...prev, key]))
  }

  async function handleConfirm() {
    if (!caseItem || !therapistId) return
    setSaving(true)
    setError('')
    try {
      const res = await apiFetch('/api/v1/scheduling/assign-recurring', {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseItem.id,
          therapist_user_id: Number(therapistId),
          weekdays,
          start_time: startTime,
          end_time: endTime,
          start_date: startDate,
          end_date: endDate,
        }),
      })
      setResult(res)
      setStep(4)
      onDone?.()
    } catch (err) {
      setError(err.message || 'Could not assign schedule')
    } finally {
      setSaving(false)
    }
  }

  if (!caseItem) return null

  return (
    <section className="admin-card" style={{ maxWidth: 560 }}>
      <h2 className="admin-card__title">Assign recurring schedule</h2>
      <p className="admin-card__subtitle">
        Book all matching slots for {caseItem.child_name || caseItem.case_code} in one step.
      </p>
      <p className="admin-form-hint" style={{ marginTop: 8 }}>
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={!therapistId} onClick={() => setQuickOpen(true)}>
          Quick recurring (streamlined)
        </button>
      </p>
      {error ? <p className="admin-form-error">{error}</p> : null}

      {step === 0 && (
        <div className="admin-form-stack">
          <p className="admin-form-hint">Child: {caseItem.child_name || caseItem.case_code}</p>
          <label className="admin-label">
            Therapist
            <AdminTherapistPicker value={therapistId} onChange={setTherapistId} />
          </label>
          <button type="button" className="admin-btn admin-btn--primary" disabled={!therapistId} onClick={() => setStep(1)}>
            Next
          </button>
        </div>
      )}

      {step === 1 && (
        <div className="admin-form-stack">
          <p className="admin-form-hint">Select days</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {WEEKDAY_KEYS.map((key, i) => (
              <button
                key={key}
                type="button"
                className={`admin-btn admin-btn--sm ${weekdays.includes(key) ? 'admin-btn--primary' : ''}`}
                onClick={() => toggleDay(key)}
              >
                {WEEKDAY_LABELS[i]}
              </button>
            ))}
          </div>
          <div className="admin-btn-group">
            <button type="button" className="admin-btn" onClick={() => setStep(0)}>
              Back
            </button>
            <button
              type="button"
              className="admin-btn admin-btn--primary"
              disabled={!weekdays.length}
              onClick={() => setStep(2)}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="admin-form-stack">
          <label className="admin-label">
            Start time
            <input type="time" className="admin-input" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </label>
          <label className="admin-label">
            End time
            <input type="time" className="admin-input" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </label>
          <div className="admin-btn-group">
            <button type="button" className="admin-btn" onClick={() => setStep(1)}>
              Back
            </button>
            <button type="button" className="admin-btn admin-btn--primary" onClick={() => setStep(3)}>
              Next
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="admin-form-stack">
          <label className="admin-label">
            From
            <input type="date" className="admin-input" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label className="admin-label">
            To
            <input type="date" className="admin-input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
          <div className="admin-review-box" style={{ fontSize: '0.85rem' }}>
            <p>
              <strong>{caseItem.child_name || caseItem.case_code}</strong> with therapist #{therapistId}
            </p>
            <p>
              {weekdays.join(', ')} · {startTime}–{endTime}
            </p>
            <p>
              {startDate} → {endDate}
            </p>
          </div>
          <div className="admin-btn-group">
            <button type="button" className="admin-btn" onClick={() => setStep(2)}>
              Back
            </button>
            <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={handleConfirm}>
              {saving ? 'Booking…' : 'Confirm & book all'}
            </button>
          </div>
        </div>
      )}

      {step === 4 && result && (
        <div className="admin-form-stack">
          <p className="admin-success">
            Booked {result.booked_slot_count} session(s). Group ID: {result.recurrence_group_id}
          </p>
          <button type="button" className="admin-btn admin-btn--primary" onClick={() => setStep(0)}>
            Assign another
          </button>
        </div>
      )}
      <QuickRecurringModal
        open={quickOpen}
        onClose={() => setQuickOpen(false)}
        fixedCaseId={caseItem?.id}
        therapistUserId={therapistId ? Number(therapistId) : undefined}
        onSuccess={() => {
          onDone?.()
          setQuickOpen(false)
        }}
      />
    </section>
  )
}
