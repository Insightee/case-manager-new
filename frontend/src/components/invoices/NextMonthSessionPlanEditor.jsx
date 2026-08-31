import { useState } from 'react'

/**
 * Homecare-only: therapists can draft next month's session plan while generating this month's invoice.
 * Informational — not billed in the current payout.
 */
export function NextMonthSessionPlanEditor({ plan, onChange }) {
  const [draftDate, setDraftDate] = useState('')
  const [draftStart, setDraftStart] = useState('09:00')
  const [draftEnd, setDraftEnd] = useState('10:00')
  const [draftNote, setDraftNote] = useState('')

  const sessions = plan?.sessions || []
  const notes = plan?.notes || ''

  function emit(next) {
    onChange?.(next)
  }

  function addSession() {
    if (!draftDate) return
    emit({
      notes,
      sessions: [
        ...sessions,
        {
          date: draftDate,
          start_time: draftStart || null,
          end_time: draftEnd || null,
          note: draftNote.trim() || null,
        },
      ],
    })
    setDraftDate('')
    setDraftNote('')
  }

  function removeSession(idx) {
    emit({
      notes,
      sessions: sessions.filter((_, i) => i !== idx),
    })
  }

  return (
    <div className="rounded-xl border border-sky-100 bg-sky-50/70 p-3">
      <p className="text-sm font-semibold text-sky-950">Next month session plan</p>
      <p className="mt-1 text-xs text-sky-900/80">
        Plan homecare visits for next month. This is saved on your invoice for reference — it is not billed this month.
      </p>

      {sessions.length ? (
        <ul className="mt-3 space-y-2">
          {sessions.map((s, idx) => (
            <li
              key={`${s.date}-${idx}`}
              className="flex items-center justify-between gap-2 rounded-lg border border-sky-100 bg-white px-3 py-2 text-sm"
            >
              <span>
                {s.date}
                {s.start_time ? ` · ${s.start_time}` : ''}
                {s.end_time ? `–${s.end_time}` : ''}
                {s.note ? ` · ${s.note}` : ''}
              </span>
              <button
                type="button"
                className="min-h-[44px] min-w-[44px] text-xs font-semibold text-rose-600"
                onClick={() => removeSession(idx)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className="text-xs font-medium text-slate-700">
          Date
          <input
            type="date"
            value={draftDate}
            onChange={(e) => setDraftDate(e.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-lg border border-[#E2E8F0] px-3 text-sm"
          />
        </label>
        <label className="text-xs font-medium text-slate-700">
          Note (optional)
          <input
            type="text"
            value={draftNote}
            onChange={(e) => setDraftNote(e.target.value)}
            placeholder="e.g. morning slot"
            className="mt-1 min-h-[44px] w-full rounded-lg border border-[#E2E8F0] px-3 text-sm"
          />
        </label>
        <label className="text-xs font-medium text-slate-700">
          Start
          <input
            type="time"
            value={draftStart}
            onChange={(e) => setDraftStart(e.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-lg border border-[#E2E8F0] px-3 text-sm"
          />
        </label>
        <label className="text-xs font-medium text-slate-700">
          End
          <input
            type="time"
            value={draftEnd}
            onChange={(e) => setDraftEnd(e.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-lg border border-[#E2E8F0] px-3 text-sm"
          />
        </label>
      </div>

      <button
        type="button"
        onClick={addSession}
        disabled={!draftDate}
        className="mt-3 min-h-[44px] w-full rounded-xl border border-sky-200 bg-white px-3 text-sm font-semibold text-sky-900 disabled:opacity-50"
      >
        + Add planned session
      </button>

      <label className="mt-3 block text-xs font-medium text-slate-700">
        Plan notes
        <textarea
          className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
          rows={2}
          value={notes}
          onChange={(e) => emit({ notes: e.target.value, sessions })}
          placeholder="Anything finance or your CM should know about next month"
        />
      </label>
    </div>
  )
}
