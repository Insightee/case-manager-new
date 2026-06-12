import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate, formatDisplayDateTimeRange } from '../../lib/datetime.js'
import { caseServiceLine } from '../../lib/leaveFormUtils.js'
import { TherapistLeaveRequestFields } from './TherapistLeaveRequestFields.jsx'
import './therapist-leave.css'

function sliceTime(t) {
  if (!t) return ''
  return String(t).slice(0, 5)
}

export function SessionAbsenceSheet({
  sessions = [],
  selectedSessionId,
  onSessionChange,
  lockedCase = null,
  assignedCases = [],
  onSuccess,
  onError,
  disabled = false,
}) {
  const [absenceType, setAbsenceType] = useState('THERAPIST_LEAVE')
  const [reason, setReason] = useState('')
  const [billingCategory, setBillingCategory] = useState('PAID')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [caseIds, setCaseIds] = useState([])
  const [startTime, setStartTime] = useState('')
  const [endTime, setEndTime] = useState('')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')

  const sessionId = selectedSessionId || (sessions[0]?.id ?? null)
  const session = sessions.find((s) => s.id === sessionId) || sessions[0]

  useEffect(() => {
    if (!session) return
    setStartDate(session.scheduled_date || '')
    setEndDate(session.scheduled_date || '')
    setStartTime(sliceTime(session.start_time))
    setEndTime(sliceTime(session.end_time))
    if (lockedCase?.id) setCaseIds([Number(lockedCase.id)])
  }, [session?.id, session?.scheduled_date, session?.start_time, session?.end_time, lockedCase?.id])

  const activeCase = useMemo(() => {
    if (lockedCase) return lockedCase
    const id = caseIds[0]
    return assignedCases.find((c) => Number(c.id) === Number(id)) || null
  }, [lockedCase, caseIds, assignedCases])

  async function patchSessionTimesIfNeeded() {
    if (!sessionId || !session) return
    const nextStart = startTime || null
    const nextEnd = endTime || null
    const prevStart = sliceTime(session.start_time) || null
    const prevEnd = sliceTime(session.end_time) || null
    if (nextStart === prevStart && nextEnd === prevEnd) return
    await apiFetch(`/api/v1/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        start_time: nextStart,
        end_time: nextEnd,
      }),
    })
  }

  async function submitTherapistLeave(e) {
    e.preventDefault()
    if (!startDate || !endDate) {
      setLocalError('Choose from and to dates.')
      return
    }
    if (endDate < startDate) {
      setLocalError('End date must be on or after start date.')
      return
    }
    const targets = lockedCase
      ? [lockedCase]
      : caseIds.length
        ? caseIds.map((id) => assignedCases.find((c) => Number(c.id) === Number(id))).filter(Boolean)
        : []
    if (assignedCases.length && !targets.length) {
      setLocalError('Select at least one case.')
      return
    }

    setBusy(true)
    setLocalError('')
    try {
      await patchSessionTimesIfNeeded()
      const rows = targets.length ? targets : [null]
      for (const caseRow of rows) {
        const serviceLine = caseRow ? caseServiceLine(caseRow) : 'shadow_support'
        let cat = 'UNPAID'
        if (serviceLine === 'shadow_support') cat = billingCategory
        await apiFetch('/api/v1/leave', {
          method: 'POST',
          body: JSON.stringify({
            service_line: serviceLine,
            billing_category: cat,
            case_id: caseRow ? Number(caseRow.id) : null,
            start_date: startDate,
            end_date: endDate,
            reason: reason.trim() || null,
          }),
        })
      }
      setReason('')
      onSuccess?.('Leave request submitted — admin will review.')
    } catch (err) {
      const msg = err.message || 'Could not submit leave'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  async function submitChildAbsent(e) {
    e.preventDefault()
    if (!sessionId) {
      setLocalError('Choose a scheduled visit for today.')
      return
    }
    setBusy(true)
    setLocalError('')
    try {
      await patchSessionTimesIfNeeded()
      await apiFetch(`/api/v1/sessions/${sessionId}/absence`, {
        method: 'POST',
        body: JSON.stringify({
          absence_type: 'CLIENT_ABSENT',
          reason: reason.trim() || null,
        }),
      })
      setReason('')
      onSuccess?.('Child absent logged — parent or admin will review.')
    } catch (err) {
      const msg = err.message || 'Could not submit child absent'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  if (!sessions.length) {
    return (
      <p className="ic-session-composer__hint">
        No scheduled visit today for this client. Pick a client with a visit on today&apos;s date.
      </p>
    )
  }

  return (
    <div className="ic-session-composer__absence">
      <div className="ic-segment ic-segment--absence" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={absenceType === 'THERAPIST_LEAVE'}
          className={absenceType === 'THERAPIST_LEAVE' ? 'active' : ''}
          onClick={() => setAbsenceType('THERAPIST_LEAVE')}
          disabled={disabled || busy}
        >
          Therapist leave
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={absenceType === 'CLIENT_ABSENT'}
          className={absenceType === 'CLIENT_ABSENT' ? 'active' : ''}
          onClick={() => setAbsenceType('CLIENT_ABSENT')}
          disabled={disabled || busy}
        >
          Child absent
        </button>
      </div>

      {sessions.length > 1 ? (
        <label className="ic-session-composer__field" style={{ marginTop: 12 }}>
          <span>Today&apos;s visit</span>
          <select
            value={sessionId || ''}
            onChange={(e) => onSessionChange?.(Number(e.target.value))}
            className="ic-session-composer__input"
            disabled={disabled || busy}
          >
            {sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {formatDisplayDateTimeRange(s.scheduled_date, s.start_time, s.end_time)} · {s.mode}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="ic-session-composer__visit-meta">
        {activeCase || session?.child_name ? (
          <div className="ic-session-composer__visit-row">
            <span className="ic-session-composer__visit-label">Client</span>
            <strong>{activeCase?.child_name || session?.child_name}</strong>
          </div>
        ) : null}
        <div className="ic-session-composer__visit-row">
          <span className="ic-session-composer__visit-label">Session date</span>
          <strong>{formatDisplayDate(session?.scheduled_date)}</strong>
        </div>
        <div className="ic-session-composer__time-grid">
          <label className="ic-session-composer__field">
            <span>Start time</span>
            <input
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="ic-session-composer__input"
              disabled={disabled || busy}
            />
          </label>
          <label className="ic-session-composer__field">
            <span>End time</span>
            <input
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="ic-session-composer__input"
              disabled={disabled || busy}
            />
          </label>
        </div>
      </div>

      {absenceType === 'THERAPIST_LEAVE' ? (
        <form onSubmit={submitTherapistLeave} style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
          <TherapistLeaveRequestFields
            assignedCases={assignedCases}
            caseIds={caseIds}
            onCaseIdsChange={setCaseIds}
            lockedCase={lockedCase}
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
            billingCategory={billingCategory}
            onBillingCategoryChange={setBillingCategory}
            reason={reason}
            onReasonChange={setReason}
            disabled={disabled || busy}
          />
          {localError ? <p className="ic-session-composer__error">{localError}</p> : null}
          <p className="ic-session-composer__hint">
            Same as Leave module — HR reviews before sessions are cancelled.
          </p>
          <button type="submit" className="therapist-leave-page__request-btn" disabled={disabled || busy}>
            {busy ? 'Submitting…' : 'Submit leave request'}
          </button>
        </form>
      ) : (
        <form onSubmit={submitChildAbsent} style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
          <label className="ic-session-composer__field">
            <span>Reason</span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="ic-session-composer__input"
              rows={3}
              placeholder="e.g. unwell, family travel — shown on the log as child absent"
              disabled={disabled || busy}
            />
          </label>
          {localError ? <p className="ic-session-composer__error">{localError}</p> : null}
          <p className="ic-session-composer__hint">Parent or admin must approve before billing is updated.</p>
          <button type="submit" className="ic-btn ic-btn--primary ic-session-composer__submit" disabled={disabled || busy}>
            {busy ? 'Submitting…' : 'Log child absent'}
          </button>
        </form>
      )}
    </div>
  )
}
