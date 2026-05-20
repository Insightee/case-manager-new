import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { WEEKDAY_KEYS, WEEKDAY_LABELS, dateStr } from './slotCalendarUtils.js'

function normalizeTime(t) {
  if (!t) return '09:00:00'
  return t.length === 5 ? `${t}:00` : t
}

function previewDates(weekdays, fromStr, toStr) {
  const out = []
  const start = new Date(fromStr + 'T12:00:00')
  const end = new Date(toStr + 'T12:00:00')
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return out
  const keys = new Set(weekdays)
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const wk = WEEKDAY_KEYS[d.getDay() === 0 ? 6 : d.getDay() - 1]
    if (keys.has(wk)) out.push(dateStr(d))
  }
  return out
}

export function QuickRecurringModal({
  open,
  onClose,
  onSuccess,
  /** When set, case picker is hidden (e.g. admin case context) */
  fixedCaseId,
  /** Required for booking; defaults to current user for therapist */
  therapistUserId: therapistUserIdProp,
}) {
  const [step, setStep] = useState(0)
  const [meId, setMeId] = useState(null)
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [therapistUserId, setTherapistUserId] = useState('')
  const [weekdays, setWeekdays] = useState(['mon', 'wed', 'fri'])
  const [startTime, setStartTime] = useState('10:00')
  const [endTime, setEndTime] = useState('11:00')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setStep(0)
    setError('')
    const today = new Date()
    const end = new Date(today)
    end.setMonth(end.getMonth() + 1)
    setStartDate(today.toISOString().slice(0, 10))
    setEndDate(end.toISOString().slice(0, 10))
    if (fixedCaseId) setCaseId(String(fixedCaseId))

    apiFetch('/api/v1/auth/me')
      .then((u) => {
        setMeId(u.id)
        if (therapistUserIdProp != null) setTherapistUserId(String(therapistUserIdProp))
        else setTherapistUserId(String(u.id))
      })
      .catch(() => {})

    const qs = therapistUserIdProp ? `?therapist_id=${therapistUserIdProp}` : ''
    apiFetch(`/api/v1/slots/bookable-cases${qs}`)
      .then(setCases)
      .catch(() => setCases([]))
  }, [open, fixedCaseId, therapistUserIdProp])

  const preview = useMemo(
    () => previewDates(weekdays, startDate, endDate),
    [weekdays, startDate, endDate],
  )

  if (!open) return null

  function toggleDay(key) {
    setWeekdays((prev) => (prev.includes(key) ? prev.filter((d) => d !== key) : [...prev, key]))
  }

  async function bookAll() {
    const cid = fixedCaseId ?? Number(caseId)
    const tid = Number(therapistUserId || meId)
    if (!cid || !tid) {
      setError('Select a case')
      return
    }
    if (!weekdays.length) {
      setError('Select at least one weekday')
      return
    }
    setLoading(true)
    setError('')
    try {
      await apiFetch('/api/v1/scheduling/assign-recurring', {
        method: 'POST',
        body: JSON.stringify({
          case_id: cid,
          therapist_user_id: tid,
          weekdays,
          start_time: normalizeTime(startTime),
          end_time: normalizeTime(endTime),
          start_date: startDate,
          end_date: endDate,
        }),
      })
      onSuccess?.()
      onClose?.()
    } catch (err) {
      setError(err.message || 'Could not book recurring sessions')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-slate-900">Quick recurring</h2>
        <p className="mt-1 text-sm text-slate-500">Book all matching slots in range (uses your availability).</p>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

        {step === 0 && (
          <div className="mt-4 space-y-3">
            <p className="text-sm font-medium text-slate-700">Pattern</p>
            <div className="flex flex-wrap gap-2">
              {WEEKDAY_KEYS.map((key, i) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => toggleDay(key)}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                    weekdays.includes(key) ? 'border-indigo-600 bg-indigo-50 text-indigo-800' : 'border-slate-200 text-slate-600'
                  }`}
                >
                  {WEEKDAY_LABELS[i]}
                </button>
              ))}
            </div>
            <div className="flex gap-2 pt-2">
              <button type="button" className="flex-1 rounded-xl border py-2 text-sm font-semibold" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                disabled={!weekdays.length}
                className="flex-1 rounded-xl bg-indigo-600 py-2 text-sm font-semibold text-white disabled:opacity-50"
                onClick={() => setStep(1)}
              >
                Next
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="mt-4 space-y-3">
            <p className="text-sm font-medium text-slate-700">Time</p>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm text-slate-600">
                Start
                <input
                  type="time"
                  className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-2 py-2 text-sm"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                />
              </label>
              <label className="text-sm text-slate-600">
                End
                <input
                  type="time"
                  className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-2 py-2 text-sm"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                />
              </label>
            </div>
            <p className="text-xs text-slate-500">About {preview.length} session dates in range (before slot conflicts).</p>
            <div className="flex gap-2 pt-2">
              <button type="button" className="flex-1 rounded-xl border py-2 text-sm font-semibold" onClick={() => setStep(0)}>
                Back
              </button>
              <button type="button" className="flex-1 rounded-xl bg-indigo-600 py-2 text-sm font-semibold text-white" onClick={() => setStep(2)}>
                Next
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="mt-4 space-y-3">
            <p className="text-sm font-medium text-slate-700">Range & case</p>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm text-slate-600">
                From
                <input
                  type="date"
                  className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-2 py-2 text-sm"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </label>
              <label className="text-sm text-slate-600">
                To
                <input
                  type="date"
                  className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-2 py-2 text-sm"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </label>
            </div>
            {fixedCaseId ? (
              <p className="text-sm text-slate-600">Case #{fixedCaseId}</p>
            ) : (
              <label className="block text-sm font-medium text-slate-700">
                Case
                <select
                  className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
                  value={caseId}
                  onChange={(e) => setCaseId(e.target.value)}
                  required
                >
                  <option value="">Select case…</option>
                  {cases.map((c) => (
                    <option key={c.case_id} value={c.case_id}>
                      {c.case_code} · {c.child_name || 'Client'}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="max-h-28 overflow-y-auto rounded-lg border border-slate-100 bg-slate-50 p-2 text-[11px] text-slate-600">
              {preview.slice(0, 24).join(', ')}
              {preview.length > 24 ? ` … +${preview.length - 24} more` : null}
            </div>
            <div className="flex gap-2 pt-2">
              <button type="button" className="flex-1 rounded-xl border py-2 text-sm font-semibold" onClick={() => setStep(1)}>
                Back
              </button>
              <button
                type="button"
                disabled={loading || (!fixedCaseId && !caseId)}
                className="flex-1 rounded-xl bg-indigo-600 py-2 text-sm font-semibold text-white disabled:opacity-50"
                onClick={bookAll}
              >
                {loading ? 'Booking…' : 'Book all'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
