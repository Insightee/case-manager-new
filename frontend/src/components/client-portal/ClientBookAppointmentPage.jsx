import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/apiClient.js'
import { useParentPortal } from '../../hooks/useParentPortal.js'
import { fetchParentAppointments } from '../../lib/parentCases.js'
import { queryKeys } from '../../lib/queryClient.js'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { ErrorBanner } from '../shared/ErrorBanner.jsx'
import { AddToGoogleCalendarButton } from '../shared/AddToGoogleCalendarButton.jsx'
import { mapParentApptToCalendarEvent } from '../../lib/googleCalendar.js'
import { formatDisplayDateLabel } from '../../lib/datetime.js'
import { ParentBookSessionForm } from './ParentBookSessionForm.jsx'
import './parent-book-form.css'
import './parent-schedule-page.css'

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
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const titleId = 'parent-appt-sheet-title'
  const calendarEvent = mapParentApptToCalendarEvent(appt)

  return createPortal(
    <div className="parent-appt-sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
      <button
        type="button"
        className="parent-appt-sheet__backdrop"
        aria-label="Close appointment details"
        onClick={onClose}
      />
      <div
        className="parent-appt-sheet__panel"
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        {appt.isCmMeeting ? (
          <>
            <p className="parent-appt-sheet__eyebrow parent-appt-sheet__eyebrow--cm">Case manager meeting</p>
            <h3 id={titleId} className="parent-appt-sheet__title">
              {formatDisplayDateLabel(appt.slotDate)}
            </h3>
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
            {calendarEvent ? (
              <div style={{ marginBottom: 12 }}>
                <AddToGoogleCalendarButton event={calendarEvent} className="w-full" />
              </div>
            ) : null}
            <button type="button" className="parent-appt-sheet__close-only" onClick={onClose}>
              Close
            </button>
          </>
        ) : (
          <>
            <p className="parent-appt-sheet__eyebrow">Therapy session</p>
            <h3 id={titleId} className="parent-appt-sheet__title">
              {formatDisplayDateLabel(appt.slotDate)}
            </h3>
            <p className="parent-appt-sheet__time">
              {appt.startTime}
              {appt.endTime ? `–${appt.endTime}` : ''}
            </p>
            {appt.childName ? <p className="parent-appt-sheet__child">Therapy · {appt.childName}</p> : null}
            {appt.therapistName ? (
              <p className="parent-appt-sheet__with">Therapist: {appt.therapistName}</p>
            ) : null}
            {calendarEvent ? (
              <div style={{ marginBottom: 12 }}>
                <AddToGoogleCalendarButton event={calendarEvent} className="w-full" />
              </div>
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
    </div>,
    document.body,
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
      subtitle="Upcoming visits and booking."
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

        <section className="parent-schedule-page__tile" aria-labelledby="parent-schedule-upcoming">
          <div className="parent-schedule-page__tile-head">
            <h2 id="parent-schedule-upcoming" className="parent-schedule-page__section-title">
              Upcoming
            </h2>
          </div>
          {apptLoading ? (
            <p className="parent-schedule-page__muted">Loading…</p>
          ) : appointments.length === 0 ? (
            <p className="parent-schedule-page__empty">Nothing booked yet — pick a time below.</p>
          ) : (
            <div className="parent-schedule-page__list">
              {appointments.map((appt) => (
                <button
                  key={appt.id}
                  type="button"
                  className={`parent-schedule-page__card ${appt.isCmMeeting ? 'parent-schedule-page__card--cm' : ''}`}
                  onClick={() => setSelectedAppt(appt)}
                >
                  <p className="parent-schedule-page__card-date">{formatDisplayDateLabel(appt.slotDate)}</p>
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

        <section className="parent-schedule-page__tile" aria-labelledby="parent-schedule-book">
          <div className="parent-schedule-page__tile-head">
            <h2 id="parent-schedule-book" className="parent-schedule-page__section-title">
              {rescheduleFrom ? 'New time' : 'Book session'}
            </h2>
          </div>
          {!rescheduleFrom ? (
            <p className="parent-schedule-page__hint">
              Therapy sessions with your assigned therapist. Case manager meetings are scheduled by the clinic.
            </p>
          ) : null}
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

    </ClientPortalLayout>
  )
}
