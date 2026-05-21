import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { STATUS_LABELS } from './slotCalendarUtils.js'

const MODULE_LABELS = {
  homecare: 'Homecare',
  shadow_support: 'Shadow care',
  counselling: 'Counselling',
  special_education: 'Special Ed',
  behaviour_therapy: 'Behaviour',
  tutoring: 'Tutoring',
  other: 'Other',
}

const MODULE_COLOURS = {
  homecare: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  shadow_support: 'bg-violet-50 text-violet-800 border-violet-200',
  counselling: 'bg-sky-50 text-sky-800 border-sky-200',
  special_education: 'bg-amber-50 text-amber-800 border-amber-200',
  behaviour_therapy: 'bg-rose-50 text-rose-800 border-rose-200',
  tutoring: 'bg-teal-50 text-teal-800 border-teal-200',
  other: 'bg-slate-50 text-slate-700 border-slate-200',
}

function diffMins(start, end) {
  if (!start || !end) return null
  const [sh, sm] = start.split(':').map(Number)
  const [eh, em] = end.split(':').map(Number)
  const d = eh * 60 + em - (sh * 60 + sm)
  return d > 0 ? d : null
}

function fmtDuration(mins) {
  if (!mins) return null
  if (mins < 60) return `${mins} min`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m ? `${h}h ${m}m` : `${h}h`
}

export function SlotDetailSheet({ open, slot, onClose, onBook, onChanged }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [caseDetail, setCaseDetail] = useState(null)
  const [moreOpen, setMoreOpen] = useState(false)
  const moreRef = useRef(null)

  // Close "more" dropdown on outside click
  useEffect(() => {
    if (!moreOpen) return
    function handle(e) {
      if (moreRef.current && !moreRef.current.contains(e.target)) setMoreOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [moreOpen])

  // Fetch case detail when a booked slot opens
  useEffect(() => {
    if (!open || !slot?.case_id) { setCaseDetail(null); return }
    apiFetch(`/api/v1/cases/${slot.case_id}`)
      .then(setCaseDetail)
      .catch(() => setCaseDetail(null))
  }, [open, slot?.case_id])

  if (!open || !slot) return null

  const pendingTherapist = slot.status === 'BOOKED' && slot.approval_status === 'PENDING_THERAPIST'
  const durMins = diffMins(slot.start_time, slot.end_time)
  const serviceModule = slot.product_module || slot.service_type || caseDetail?.product_module
  const moduleLabel = serviceModule ? (MODULE_LABELS[serviceModule] || serviceModule) : null
  const moduleColour = MODULE_COLOURS[serviceModule] || MODULE_COLOURS.other

  // Address display — client's homecare/shadow visit address
  const addr = caseDetail?.service_address
  const showAddress = addr && ['homecare', 'shadow_support'].includes(serviceModule)

  async function run(action) {
    setBusy(true)
    setError('')
    setMoreOpen(false)
    try {
      if (action === 'book') { onBook?.(slot); return }
      if (action === 'edit') { onChanged?.('edit', slot); return }
      if (action === 'confirm_reschedule') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/confirm-reschedule`, { method: 'POST' })
      } else if (action === 'decline_reschedule') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/decline-reschedule`, { method: 'POST' })
      } else if (action === 'cancel') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/cancel`, { method: 'POST' })
      } else if (action === 'block') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/block`, { method: 'POST' })
      } else if (action === 'delete') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}`, { method: 'DELETE' })
      }
      onChanged?.('refresh')
      onClose()
    } catch (err) {
      setError(err.message || 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleStartSession() {
    if (!slot.session_id) { setError('No linked session found for this slot.'); return }
    setBusy(true)
    setError('')
    try {
      await apiFetch(`/api/v1/sessions/${slot.session_id}/start`, { method: 'POST', body: JSON.stringify({}) })
      onClose()
      navigate('/therapist/logs')
    } catch (err) {
      setError(err.message || 'Could not start session')
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white shadow-xl sm:rounded-2xl overflow-y-auto max-h-[90vh]">
        {/* ── Header ── */}
        <div className="px-6 pt-5 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {STATUS_LABELS[slot.status] || slot.status}
            </span>
            {moduleLabel ? (
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${moduleColour}`}>
                {moduleLabel}
              </span>
            ) : null}
            {durMins ? (
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {fmtDuration(durMins)}
              </span>
            ) : null}
          </div>
          <h2 className="text-lg font-bold text-slate-900">
            {slot.slot_date} · {slot.start_time}–{slot.end_time}
          </h2>
          {slot.child_name || slot.case_code ? (
            <p className="mt-0.5 text-sm font-medium text-slate-700">
              {slot.child_name || slot.case_code}
            </p>
          ) : null}
          {pendingTherapist ? (
            <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Parent requested a time change. Confirm to keep the new slot, or decline to revert.
            </p>
          ) : null}
          {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}
        </div>

        {/* ── Client card (BOOKED only) ── */}
        {slot.status === 'BOOKED' && caseDetail ? (
          <div className="px-6 py-4 border-b border-slate-100 space-y-3">
            {/* Parent info */}
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Client</p>
              {caseDetail.parent_name ? (
                <p className="text-sm font-medium text-slate-800">{caseDetail.parent_name}</p>
              ) : null}
              {caseDetail.parent_phone ? (
                <a
                  href={`tel:${caseDetail.parent_phone}`}
                  className="block text-sm text-indigo-600 hover:underline"
                >
                  {caseDetail.parent_phone}
                </a>
              ) : null}
              {caseDetail.parent_email ? (
                <a
                  href={`mailto:${caseDetail.parent_email}`}
                  className="block text-sm text-slate-600 hover:underline"
                >
                  {caseDetail.parent_email}
                </a>
              ) : null}
              {slot.case_id ? (
                <a
                  href={`/admin/cases/${slot.case_id}`}
                  className="mt-1 inline-block text-xs font-semibold text-indigo-600 hover:underline"
                  onClick={(e) => { e.preventDefault(); onClose(); navigate(`/admin/cases/${slot.case_id}`) }}
                >
                  View case →
                </a>
              ) : null}
            </div>

            {/* Visit address (homecare / shadow only) */}
            {showAddress ? (
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700 mb-1">Visit address</p>
                <p className="text-sm text-slate-800">
                  {addr.formatted || [addr.address_line1, addr.city, addr.pincode].filter(Boolean).join(', ')}
                </p>
                {caseDetail.maps_url ? (
                  <a
                    href={caseDetail.maps_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-block text-xs font-semibold text-emerald-700 hover:underline"
                  >
                    Open in Maps ↗
                  </a>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {/* ── Actions ── */}
        <div className="px-6 py-4 flex flex-col gap-2">
          {/* AVAILABLE slot actions */}
          {slot.status === 'AVAILABLE' && (
            <>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] w-full rounded-xl bg-indigo-600 text-sm font-semibold text-white disabled:opacity-50"
                onClick={() => run('book')}
              >
                Book client
              </button>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] w-full rounded-xl border border-slate-200 text-sm font-semibold text-slate-700"
                onClick={() => run('edit')}
              >
                Edit time
              </button>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] w-full rounded-xl border border-slate-200 text-sm font-semibold text-slate-600"
                onClick={() => run('block')}
              >
                Block slot
              </button>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] w-full rounded-xl border border-red-100 text-sm font-semibold text-red-600"
                onClick={() => run('delete')}
              >
                Remove slot
              </button>
            </>
          )}

          {/* BOOKED slot actions */}
          {slot.status === 'BOOKED' && (
            <>
              {pendingTherapist ? (
                <>
                  <button
                    type="button"
                    disabled={busy}
                    className="min-h-[44px] w-full rounded-xl bg-indigo-600 text-sm font-semibold text-white disabled:opacity-50"
                    onClick={() => run('confirm_reschedule')}
                  >
                    Confirm new time
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className="min-h-[44px] w-full rounded-xl border border-amber-300 text-sm font-semibold text-amber-900"
                    onClick={() => run('decline_reschedule')}
                  >
                    Decline reschedule
                  </button>
                </>
              ) : (
                <>
                  {/* Primary: Start Session */}
                  {slot.session_id ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={handleStartSession}
                      className="min-h-[44px] w-full rounded-xl bg-indigo-600 text-sm font-semibold text-white disabled:opacity-50"
                    >
                      Start session
                    </button>
                  ) : null}

                  {/* Secondary: More actions dropdown */}
                  <div className="relative" ref={moreRef}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setMoreOpen((v) => !v)}
                      className="min-h-[44px] w-full rounded-xl border border-slate-200 text-sm font-semibold text-slate-700 flex items-center justify-center gap-1"
                    >
                      More actions
                      <svg
                        className={`h-4 w-4 transition-transform ${moreOpen ? 'rotate-180' : ''}`}
                        viewBox="0 0 20 20"
                        fill="currentColor"
                      >
                        <path
                          fillRule="evenodd"
                          d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </button>
                    {moreOpen && (
                      <div className="absolute bottom-full mb-1 left-0 right-0 rounded-xl border border-slate-200 bg-white shadow-lg overflow-hidden z-10">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => run('edit')}
                          className="w-full px-4 py-3 text-left text-sm font-medium text-slate-700 hover:bg-slate-50"
                        >
                          Edit time
                        </button>
                        <div className="border-t border-slate-100" />
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => run('cancel')}
                          className="w-full px-4 py-3 text-left text-sm font-medium text-red-600 hover:bg-red-50"
                        >
                          Cancel booking
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {/* BLOCKED slot */}
          {slot.status === 'BLOCKED' && (
            <button
              type="button"
              disabled={busy}
              className="min-h-[44px] w-full rounded-xl border border-slate-200 text-sm font-semibold text-slate-700"
              onClick={() => run('delete')}
            >
              Unblock / remove
            </button>
          )}

          <button
            type="button"
            className="min-h-[44px] text-sm text-slate-400 hover:text-slate-600"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
