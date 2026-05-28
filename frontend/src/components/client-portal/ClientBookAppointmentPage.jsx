import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/apiClient.js'
import { useParentPortal } from '../../hooks/useParentPortal.js'
import { fetchParentAppointments } from '../../lib/parentCases.js'
import { queryKeys } from '../../lib/queryClient.js'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { ErrorBanner } from '../shared/ErrorBanner.jsx'
import { ParentBookSessionForm } from './ParentBookSessionForm.jsx'
import './parent-book-form.css'

function fmtDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function ApptStatusBadge({ status }) {
  if (status === 'PENDING_THERAPIST') {
    return (
      <span className="parent-appt-badge parent-appt-badge--pending">Pending approval</span>
    )
  }
  if (status === 'CANCELLED') {
    return (
      <span className="parent-appt-badge parent-appt-badge--cancelled">Cancelled</span>
    )
  }
  return <span className="parent-appt-badge parent-appt-badge--ok">Confirmed</span>
}

function UpcomingApptSheet({ appt, onReschedule, onCancel, onClose, acting }) {
  return (
    <div className="parent-appt-sheet" role="dialog" aria-modal="true">
      <div className="parent-appt-sheet__panel">
        {appt.isCmMeeting ? (
          <>
            <p className="parent-appt-sheet__eyebrow parent-appt-sheet__eyebrow--cm">Case manager meeting</p>
            <h3 className="parent-appt-sheet__title">{fmtDate(appt.slotDate)}</h3>
            <p className="parent-appt-sheet__time">
              {appt.startTime}
              {appt.endTime ? `–${appt.endTime}` : ''}
            </p>
            {appt.caseMgrName ? (
              <p className="parent-appt-sheet__with">With: {appt.caseMgrName}</p>
            ) : null}
            <p className="parent-appt-sheet__hint">
              Booked by your case manager. Contact them to change this meeting — therapy sessions are booked below.
            </p>
            <button type="button" className="parent-appt-sheet__close-only" onClick={onClose}>
              Close
            </button>
          </>
        ) : (
          <>
            <p className="parent-appt-sheet__eyebrow">Therapy session</p>
            <h3 className="parent-appt-sheet__title">{fmtDate(appt.slotDate)}</h3>
            <p className="parent-appt-sheet__time">
              {appt.startTime}
              {appt.endTime ? `–${appt.endTime}` : ''}
            </p>
            {appt.childName ? <p className="parent-appt-sheet__child">Therapy · {appt.childName}</p> : null}
            {appt.therapistName ? (
              <p className="parent-appt-sheet__with">Therapist: {appt.therapistName}</p>
            ) : null}
            <div className="parent-appt-sheet__actions">
              <button
                type="button"
                disabled={!appt.canReschedule || acting}
                title={appt.rescheduleReason || ''}
                className="parent-appt-sheet__reschedule"
                onClick={() => onReschedule(appt)}
              >
                Reschedule
              </button>
              <button
                type="button"
                disabled={!appt.canCancel || acting}
                title={appt.cancelReason || ''}
                className="parent-appt-sheet__cancel"
                onClick={() => onCancel(appt)}
              >
                Cancel session
              </button>
              <button type="button" className="parent-appt-sheet__ghost" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export function ClientBookAppointmentPage() {
  const location = useLocation()
  const queryClient = useQueryClient()
  const { cases, casesLoading } = useParentPortal()
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [formActing, setFormActing] = useState(false)
  const [rescheduleFrom, setRescheduleFrom] = useState(null)
  const [selectedAppt, setSelectedAppt] = useState(null)

  const {
    data: appointments = [],
    isLoading: apptLoading,
    error: apptQueryError,
    refetch: refetchAppointments,
  } = useQuery({
    queryKey: queryKeys.parentAppointments,
    queryFn: fetchParentAppointments,
    staleTime: 30_000,
  })

  const cancelMutation = useMutation({
    mutationFn: (rawId) =>
      apiFetch(`/api/v1/parent/appointments/${rawId}/cancel`, { method: 'POST' }),
    onSuccess: async () => {
      setMessage('Session cancelled.')
      setSelectedAppt(null)
      await queryClient.invalidateQueries({ queryKey: queryKeys.parentAppointments })
      await queryClient.invalidateQueries({ queryKey: queryKeys.parentBootstrap })
    },
    onError: (err) => setError(err.message || 'Could not cancel'),
  })

  useEffect(() => {
    const openId = location.state?.openApptId
    if (!openId || !appointments.length) return
    const match = appointments.find((a) => a.id === openId || String(a.rawId) === String(openId))
    if (match) setSelectedAppt(match)
  }, [location.state?.openApptId, appointments])

  function startRescheduleFromStrip(appt) {
    setRescheduleFrom(appt)
    setSelectedAppt(null)
    setMessage('Choose a new date and open slot below.')
  }

  const acting = cancelMutation.isPending || formActing
  const loadError = apptQueryError?.message || error

  return (
    <ClientPortalLayout
      title="Session schedule"
      subtitle="View upcoming therapy sessions and case manager meetings, or book a new therapy session."
    >
      <div className="parent-schedule-page">
        <ErrorBanner
          message={loadError}
          onRetry={() => {
            setError('')
            refetchAppointments()
          }}
        />

        {message ? <p className="parent-schedule-page__msg parent-schedule-page__msg--ok">{message}</p> : null}

        <section>
          <h2 className="parent-schedule-page__section-title">Upcoming sessions</h2>
          {apptLoading ? (
            <p className="parent-schedule-page__muted">Loading…</p>
          ) : appointments.length === 0 ? (
            <p className="parent-schedule-page__muted">No upcoming sessions booked yet.</p>
          ) : (
            <div className="parent-schedule-page__strip">
              {appointments.map((appt) => (
                <button
                  key={appt.id}
                  type="button"
                  className={`parent-schedule-page__card ${appt.isCmMeeting ? 'parent-schedule-page__card--cm' : ''}`}
                  onClick={() => setSelectedAppt(appt)}
                >
                  <p className="parent-schedule-page__card-date">{fmtDate(appt.slotDate)}</p>
                  <p className="parent-schedule-page__card-time">
                    {appt.startTime}
                    {appt.endTime ? `–${appt.endTime}` : ''}
                  </p>
                  <p className="parent-schedule-page__card-role">
                    {appt.isCmMeeting ? 'Case manager meeting' : `Therapy · ${appt.childName || '—'}`}
                  </p>
                  <p className="parent-schedule-page__card-sub">
                    {appt.isCmMeeting
                      ? appt.caseMgrName
                        ? `With: ${appt.caseMgrName}`
                        : 'With your case manager'
                      : appt.therapistName
                        ? `Therapist: ${appt.therapistName}`
                        : null}
                  </p>
                  <div>
                    {appt.isCmMeeting ? (
                      <span className="parent-appt-badge parent-appt-badge--cm">CM meeting</span>
                    ) : (
                      <ApptStatusBadge status={appt.approvalStatus} />
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        {casesLoading ? (
          <p className="parent-schedule-page__muted">Loading your cases…</p>
        ) : !cases?.length ? (
          <p className="parent-schedule-page__msg parent-schedule-page__msg--err" role="alert">
            No active cases are linked to your account yet. Contact your care team if you expected to book sessions
            here.
          </p>
        ) : null}

        <section>
          <h2 className="parent-schedule-page__section-title">
            {rescheduleFrom ? 'Pick a new time' : 'Book a new therapy session'}
          </h2>
          <ParentBookSessionForm
            cases={cases}
            rescheduleFrom={rescheduleFrom}
            onCancelReschedule={() => {
              setRescheduleFrom(null)
              setMessage('')
            }}
            onBookSuccess={async () => {
              setRescheduleFrom(null)
              setMessage('Appointment booked. Your therapist has been notified.')
              await queryClient.invalidateQueries({ queryKey: queryKeys.parentAppointments })
              await queryClient.invalidateQueries({ queryKey: queryKeys.parentBootstrap })
            }}
            onRescheduleSuccess={async () => {
              setRescheduleFrom(null)
              setMessage('Reschedule request sent — your therapist will confirm.')
              await queryClient.invalidateQueries({ queryKey: queryKeys.parentAppointments })
              await queryClient.invalidateQueries({ queryKey: queryKeys.parentBootstrap })
            }}
            acting={formActing}
            setActing={setFormActing}
            setError={setError}
            setMessage={setMessage}
          />
        </section>

        {selectedAppt ? (
          <UpcomingApptSheet
            appt={selectedAppt}
            acting={acting}
            onReschedule={startRescheduleFromStrip}
            onCancel={(appt) => cancelMutation.mutate(appt.rawId)}
            onClose={() => setSelectedAppt(null)}
          />
        ) : null}
      </div>

      <style>{`
        .parent-schedule-page { display: flex; flex-direction: column; gap: 16px; }
        .parent-schedule-page__section-title { font-size: 0.9rem; font-weight: 700; color: #475569; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.06em; }
        .parent-schedule-page__msg { border-radius: 10px; padding: 8px 12px; font-size: 0.875rem; margin: 0; }
        .parent-schedule-page__msg--ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #14532d; }
        .parent-schedule-page__msg--err { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; }
        .parent-schedule-page__muted { font-size: 0.875rem; color: #94a3b8; }
        .parent-schedule-page__strip { display: flex; gap: 10px; overflow-x: auto; padding-bottom: 4px; }
        .parent-schedule-page__card { flex: 0 0 auto; min-width: 175px; max-width: 205px; min-height: 44px; background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 12px 13px; text-align: left; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.05); -webkit-tap-highlight-color: transparent; }
        .parent-schedule-page__card--cm { background: #faf5ff; border-color: #ddd6fe; }
        .parent-schedule-page__card-date { font-size: 0.7rem; font-weight: 700; color: #4f46e5; text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 4px; }
        .parent-schedule-page__card--cm .parent-schedule-page__card-date { color: #7c3aed; }
        .parent-schedule-page__card-time { font-size: 0.875rem; font-weight: 600; color: #1e293b; margin: 0 0 4px; }
        .parent-schedule-page__card-role { font-size: 0.78rem; color: #475569; margin: 0 0 2px; font-weight: 600; }
        .parent-schedule-page__card-sub { font-size: 0.75rem; color: #94a3b8; margin: 0 0 6px; }
        .parent-appt-badge { font-size: 0.7rem; font-weight: 700; border-radius: 99px; padding: 1px 8px; border: 1px solid; }
        .parent-appt-badge--ok { background: #dcfce7; color: #14532d; border-color: #bbf7d0; }
        .parent-appt-badge--pending { background: #fef3c7; color: #92400e; border-color: #fde68a; }
        .parent-appt-badge--cancelled { background: #fee2e2; color: #991b1b; border-color: #fca5a5; }
        .parent-appt-badge--cm { background: #ede9fe; color: #4c1d95; border-color: #c4b5fd; }
        .parent-appt-sheet { position: fixed; inset: 0; z-index: 50; display: flex; align-items: flex-end; justify-content: center; background: rgba(15,23,42,0.4); padding: 16px; }
        @media (min-width: 640px) { .parent-appt-sheet { align-items: center; } }
        .parent-appt-sheet__panel { width: 100%; max-width: 420px; background: #fff; border-radius: 20px; padding: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
        .parent-appt-sheet__eyebrow { font-size: 0.7rem; font-weight: 700; color: #4f46e5; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
        .parent-appt-sheet__eyebrow--cm { color: #7c3aed; }
        .parent-appt-sheet__title { font-size: 1.1rem; font-weight: 700; color: #1e293b; margin: 0 0 4px; }
        .parent-appt-sheet__time { font-size: 0.875rem; color: #475569; margin: 0 0 4px; }
        .parent-appt-sheet__child { font-size: 0.8rem; color: #64748b; margin: 0 0 2px; }
        .parent-appt-sheet__with { font-size: 0.8rem; color: #94a3b8; margin: 0 0 16px; }
        .parent-appt-sheet__hint { font-size: 0.8rem; color: #94a3b8; margin: 0 0 16px; }
        .parent-appt-sheet__actions { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
        .parent-appt-sheet__reschedule { background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 12px; padding: 10px 0; font-weight: 600; font-size: 0.875rem; color: #3730a3; cursor: pointer; }
        .parent-appt-sheet__reschedule:disabled { opacity: 0.45; cursor: not-allowed; }
        .parent-appt-sheet__cancel { background: #fff; border: 1px solid #fca5a5; border-radius: 12px; padding: 10px 0; font-weight: 600; font-size: 0.875rem; color: #dc2626; cursor: pointer; }
        .parent-appt-sheet__cancel:disabled { opacity: 0.45; cursor: not-allowed; }
        .parent-appt-sheet__ghost, .parent-appt-sheet__close-only { background: none; border: none; font-size: 0.875rem; color: #94a3b8; cursor: pointer; padding: 6px 0; }
        .parent-appt-sheet__close-only { width: 100%; background: #f1f5f9; border-radius: 12px; padding: 10px 0; font-weight: 600; color: #475569; }
      `}</style>
    </ClientPortalLayout>
  )
}
