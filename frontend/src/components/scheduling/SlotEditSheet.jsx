import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ScheduleWeekdayPicker } from './ScheduleWeekdayPicker.jsx'
import { ONGOING_MATERIALIZE_WEEKS } from './scheduleTemplateUtils.js'
import { dateStr, weekEndContaining } from './slotCalendarUtils.js'

const DURATION_CHIPS = [
  { label: '30 min', mins: 30 },
  { label: '60 min', mins: 60 },
  { label: '90 min', mins: 90 },
  { label: '2 h', mins: 120 },
]

const SERVICE_TYPES = [
  { value: 'homecare', label: 'Homecare' },
  { value: 'shadow_support', label: 'Shadow care' },
  { value: 'counselling', label: 'Counselling' },
  { value: 'special_education', label: 'Special Education' },
  { value: 'behaviour_therapy', label: 'Behaviour Therapy' },
  { value: 'tutoring', label: 'Tutoring' },
  { value: 'other', label: 'Other' },
]

function addMinsToHM(hm, mins) {
  const [h, m] = hm.split(':').map(Number)
  const total = h * 60 + m + mins
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function diffMins(start, end) {
  if (!start || !end) return null
  const [sh, sm] = start.split(':').map(Number)
  const [eh, em] = end.split(':').map(Number)
  const d = eh * 60 + em - (sh * 60 + sm)
  return d > 0 ? d : null
}

// 3-months from today
function defaultEndDate() {
  const d = new Date()
  d.setMonth(d.getMonth() + 3)
  return d.toISOString().slice(0, 10)
}

export function SlotEditSheet({
  open,
  mode,
  slot,
  cellDate,
  cellHour,
  therapistId,
  isAdmin,
  onClose,
  onSaved,
}) {
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('10:00')
  const [notes, setNotes] = useState('')
  const [serviceType, setServiceType] = useState('')

  // Booking toggle
  const [bookClient, setBookClient] = useState(false)
  const [bookTab, setBookTab] = useState('existing') // 'existing' | 'new'

  // Existing case
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)

  // New client invite
  const [clientName, setClientName] = useState('')
  const [childName, setChildName] = useState('')
  const [clientEmail, setClientEmail] = useState('')
  const [clientPhone, setClientPhone] = useState('')

  // Recurring
  const [recurring, setRecurring] = useState(false)
  const [recurWeekdays, setRecurWeekdays] = useState([])
  const [recurScope, setRecurScope] = useState('until')
  const [recurEndDate, setRecurEndDate] = useState(defaultEndDate())

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const slotDate = mode === 'edit' && slot ? slot.slot_date : cellDate ? dateStr(cellDate) : ''

  useEffect(() => {
    if (!open) return
    setError('')
    setSaving(false)
    setRecurring(false)
    setRecurWeekdays([])
    setRecurScope('until')
    setRecurEndDate(defaultEndDate())
    setBookClient(!!isAdmin)
    setBookTab('existing')
    setCaseId('')
    setSelectedCase(null)
    setClientName('')
    setChildName('')
    setClientEmail('')
    setClientPhone('')

    if (mode === 'edit' && slot) {
      setStartTime(slot.start_time)
      setEndTime(slot.end_time)
      setNotes(slot.notes || '')
      setServiceType(slot.product_module || slot.service_type || '')
    } else {
      const hour = cellHour != null ? String(cellHour).padStart(2, '0') : '09'
      setStartTime(`${hour}:00`)
      setEndTime(addMinsToHM(`${hour}:00`, 60))
      setNotes('')
      setServiceType('')
    }
  }, [open, mode, slot, cellDate, cellHour, isAdmin])

  // Load cases when booking toggle is on
  useEffect(() => {
    if (!open || !bookClient) return
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    apiFetch(`/api/v1/slots/bookable-cases${qs}`)
      .then(setCases)
      .catch(() => setCases([]))
  }, [open, bookClient, therapistId])

  if (!open) return null

  const durMins = diffMins(startTime, endTime)

  function applyChip(mins) {
    setEndTime(addMinsToHM(startTime, mins))
  }

  function resolveRecurEndDate(fromDate) {
    if (recurScope === 'this_week') return weekEndContaining(fromDate)
    if (recurScope === 'ongoing') {
      const d = new Date(`${fromDate}T12:00:00`)
      d.setDate(d.getDate() + ONGOING_MATERIALIZE_WEEKS * 7)
      return dateStr(d)
    }
    return recurEndDate
  }

  function recurWeeksCount(fromDate) {
    if (recurScope === 'this_week') return 1
    if (recurScope === 'ongoing') return ONGOING_MATERIALIZE_WEEKS
    const start = new Date(`${fromDate}T12:00:00`)
    const end = new Date(`${recurEndDate}T12:00:00`)
    const diff = Math.max(1, Math.ceil((end - start) / (7 * 86400000)))
    return Math.min(52, diff)
  }

  async function handleSave(e) {
    e.preventDefault()
    if (!startTime || !endTime) { setError('Start and end time are required.'); return }
    if (endTime <= startTime) { setError('End time must be after start time.'); return }

    setSaving(true)
    setError('')
    try {
      // ------- Recurring path (no case booking, just open slots) -------
      if (recurring && recurWeekdays.length > 0 && !bookClient) {
        await apiFetch('/api/v1/slots/recurring', {
          method: 'POST',
          body: JSON.stringify({
            weekday_keys: recurWeekdays,
            start_time: startTime,
            end_time: endTime,
            from_date: slotDate,
            weeks: recurWeeksCount(slotDate),
            therapist_id: therapistId || undefined,
          }),
        })
        onSaved?.()
        onClose()
        return
      }

      // ------- Create/edit the single slot -------
      let savedSlot
      if (mode === 'edit' && slot) {
        savedSlot = await apiFetch(`/api/v1/scheduling/slots/${slot.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            start_time: startTime,
            end_time: endTime,
            notes: notes || null,
          }),
        })
      } else {
        savedSlot = await apiFetch('/api/v1/scheduling/slots', {
          method: 'POST',
          body: JSON.stringify({
            slot_date: slotDate,
            start_time: startTime,
            end_time: endTime,
            notes: notes || null,
            therapist_id: therapistId || undefined,
          }),
        })
      }

      const newSlotId = savedSlot?.id || slot?.id

      // ------- Book client (if toggle on) -------
      if (bookClient && newSlotId) {
        if (bookTab === 'existing' && caseId) {
          await apiFetch(`/api/v1/scheduling/slots/${newSlotId}/book`, {
            method: 'POST',
            body: JSON.stringify({ case_id: Number(caseId) }),
          })
        } else if (bookTab === 'new' && clientName && clientEmail) {
          await apiFetch(`/api/v1/scheduling/slots/${newSlotId}/invite-client`, {
            method: 'POST',
            body: JSON.stringify({
              client_name: clientName.trim(),
              client_email: clientEmail.trim(),
              child_name: childName.trim() || null,
              client_phone: clientPhone.trim() || null,
            }),
          })
        }
      }

      // ------- If recurring + case selected, also assign recurring -------
      if (recurring && recurWeekdays.length > 0 && bookClient && caseId) {
        await apiFetch('/api/v1/scheduling/assign-recurring', {
          method: 'POST',
          body: JSON.stringify({
            case_id: Number(caseId),
            therapist_user_id: therapistId || undefined,
            weekdays: recurWeekdays,
            start_time: startTime,
            end_time: endTime,
            start_date: slotDate,
            end_date: resolveRecurEndDate(slotDate),
          }),
        }).catch(() => {}) // best-effort
      }

      onSaved?.()
      onClose()
    } catch (err) {
      setError(err.message || 'Could not save slot')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white shadow-xl sm:rounded-2xl overflow-y-auto max-h-[90vh]">
        {/* Header */}
        <div className="sticky top-0 bg-white px-6 pt-5 pb-3 border-b border-slate-100">
          <h2 className="text-lg font-bold text-slate-900">{mode === 'add' ? 'Add slot' : 'Edit slot'}</h2>
          <p className="mt-0.5 text-sm text-slate-500">{slotDate}</p>
          {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}
        </div>

        <form className="px-6 pb-6 space-y-5 pt-4" onSubmit={handleSave}>
          {/* ── Section A: When ── */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Time</p>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm font-medium text-slate-700">
                Start
                <input
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  required
                />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                End
                <input
                  type="time"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  required
                />
              </label>
            </div>
            {durMins ? (
              <p className="mt-1 text-xs text-slate-400">Duration: {durMins} min</p>
            ) : null}
            {/* Duration quick-select */}
            <div className="mt-2 flex gap-2 flex-wrap">
              {DURATION_CHIPS.map((c) => (
                <button
                  key={c.mins}
                  type="button"
                  onClick={() => applyChip(c.mins)}
                  className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                    durMins === c.mins
                      ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                      : 'border-slate-200 text-slate-600 hover:border-indigo-300'
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Service type ── */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Service type</p>
            <div className="flex gap-2 flex-wrap">
              {SERVICE_TYPES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => setServiceType(serviceType === s.value ? '' : s.value)}
                  className={`rounded-full border px-3 py-1 text-xs font-semibold transition-colors ${
                    serviceType === s.value
                      ? 'border-indigo-600 bg-indigo-600 text-white'
                      : 'border-slate-200 text-slate-600 hover:border-indigo-300'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Section B: Book a client ── */}
          <div className="rounded-xl border border-slate-200 p-4">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-sm font-semibold text-slate-800">Book a client for this slot?</span>
              <button
                type="button"
                role="switch"
                aria-checked={bookClient}
                onClick={() => setBookClient((v) => !v)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  bookClient ? 'bg-indigo-600' : 'bg-slate-200'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    bookClient ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </label>

            {bookClient && (
              <div className="mt-4">
                {/* Tab row */}
                <div className="flex rounded-lg border border-slate-200 p-0.5 mb-4">
                  {[
                    { id: 'existing', label: 'Existing case' },
                    { id: 'new', label: 'New client' },
                  ].map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setBookTab(t.id)}
                      className={`flex-1 rounded-md py-1.5 text-xs font-semibold ${
                        bookTab === t.id ? 'bg-indigo-600 text-white' : 'text-slate-600'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>

                {bookTab === 'existing' ? (
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-slate-700">
                      Case
                      <select
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        value={caseId}
                        onChange={(e) => {
                          const id = e.target.value
                          setCaseId(id)
                          const c = cases.find((x) => String(x.case_id) === id) || null
                          setSelectedCase(c)
                          if (c?.product_module) setServiceType(c.product_module)
                        }}
                      >
                        <option value="">Select case…</option>
                        {cases.map((c) => (
                          <option key={c.case_id} value={c.case_id}>
                            {c.case_code} · {c.child_name || 'Client'}
                          </option>
                        ))}
                      </select>
                    </label>
                    {selectedCase?.service_address?.formatted ? (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                        <p className="font-medium text-slate-800 text-xs uppercase tracking-wide mb-1">Visit address</p>
                        <p className="text-slate-700">{selectedCase.service_address.formatted}</p>
                        {selectedCase.maps_url ? (
                          <a
                            href={selectedCase.maps_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-1 inline-block text-xs font-semibold text-indigo-600 hover:underline"
                          >
                            Open in Maps ↗
                          </a>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-xs text-slate-500">
                      We&apos;ll hold this slot and email the parent a portal invite. Admin will finalize onboarding.
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <label className="block text-sm font-medium text-slate-700">
                        Parent name
                        <input
                          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                          value={clientName}
                          onChange={(e) => setClientName(e.target.value)}
                          placeholder="e.g. Alex Smith"
                        />
                      </label>
                      <label className="block text-sm font-medium text-slate-700">
                        Child name
                        <input
                          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                          value={childName}
                          onChange={(e) => setChildName(e.target.value)}
                          placeholder="Child's name"
                        />
                      </label>
                    </div>
                    <label className="block text-sm font-medium text-slate-700">
                      Email
                      <input
                        type="email"
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        value={clientEmail}
                        onChange={(e) => setClientEmail(e.target.value)}
                        placeholder="parent@email.com"
                      />
                    </label>
                    <label className="block text-sm font-medium text-slate-700">
                      Phone (optional)
                      <input
                        type="tel"
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        value={clientPhone}
                        onChange={(e) => setClientPhone(e.target.value)}
                        placeholder="+91 98765 43210"
                      />
                    </label>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Section C: Recurring ── */}
          <div className="rounded-xl border border-slate-200 p-4">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-sm font-semibold text-slate-800">Make recurring?</span>
              <button
                type="button"
                role="switch"
                aria-checked={recurring}
                onClick={() => setRecurring((v) => !v)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  recurring ? 'bg-indigo-600' : 'bg-slate-200'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                    recurring ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </label>

            {recurring && (
              <div className="mt-4 space-y-3">
                <ScheduleWeekdayPicker value={recurWeekdays} onChange={setRecurWeekdays} compact />
                <div className="space-y-2">
                  {[
                    { id: 'this_week', label: 'This week only' },
                    { id: 'until', label: 'Until a date' },
                    { id: 'ongoing', label: `Ongoing (${ONGOING_MATERIALIZE_WEEKS} weeks ahead)` },
                  ].map((m) => (
                    <label key={m.id} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                      <input
                        type="radio"
                        name="recurScope"
                        checked={recurScope === m.id}
                        onChange={() => setRecurScope(m.id)}
                      />
                      {m.label}
                    </label>
                  ))}
                </div>
                {recurScope === 'until' ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Until
                    <input
                      type="date"
                      value={recurEndDate}
                      min={slotDate}
                      onChange={(e) => setRecurEndDate(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                  </label>
                ) : null}
                {recurScope === 'ongoing' ? (
                  <p className="text-xs text-slate-500">
                    Open slots or bookings repeat through{' '}
                    {slotDate ? resolveRecurEndDate(slotDate) : '…'} — re-run weekly schedule to extend.
                  </p>
                ) : null}
              </div>
            )}
          </div>

          {/* Notes */}
          <label className="block text-sm font-medium text-slate-700">
            Notes (optional)
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] flex-1 rounded-xl border border-slate-200 text-sm font-semibold text-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="min-h-[44px] flex-1 rounded-xl bg-indigo-600 text-sm font-semibold text-white disabled:opacity-60"
            >
              {saving ? 'Saving…' : mode === 'add' ? 'Save slot' : 'Update slot'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
