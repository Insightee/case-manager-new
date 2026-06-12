import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { formatCalendarEventWhen } from '../../lib/googleCalendar.js'
import { AddToGoogleCalendarButton } from './AddToGoogleCalendarButton.jsx'

/**
 * Post-booking confirmation — mirrors CM meeting success with session details + Google Calendar.
 */
export function BookingSuccessSheet({
  open,
  onClose,
  title = 'Session booked',
  subtitle,
  event,
  detailLines = [],
}) {
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  const when = subtitle || formatCalendarEventWhen(event)

  return createPortal(
    <div className="booking-success-sheet" role="dialog" aria-modal="true" aria-labelledby="booking-success-title">
      <button type="button" className="booking-success-sheet__backdrop" aria-label="Close" onClick={onClose} />
      <div className="booking-success-sheet__panel" onClick={(e) => e.stopPropagation()}>
        <h2 id="booking-success-title" className="booking-success-sheet__title">
          {title}
        </h2>
        {when ? <p className="booking-success-sheet__when">{when}</p> : null}
        {event?.title ? <p className="booking-success-sheet__event-title">{event.title}</p> : null}
        {detailLines.length > 0 ? (
          <ul className="booking-success-sheet__details">
            {detailLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}
        {event ? (
          <div className="booking-success-sheet__calendar">
            <AddToGoogleCalendarButton event={event} className="w-full" showHelper />
          </div>
        ) : null}
        <button type="button" className="booking-success-sheet__done" onClick={onClose}>
          Done
        </button>
      </div>
      <style>{`
        .booking-success-sheet { position: fixed; inset: 0; z-index: 220; display: flex; align-items: center; justify-content: center; padding: 16px; }
        .booking-success-sheet__backdrop { position: absolute; inset: 0; border: none; background: rgba(15,23,42,0.45); cursor: default; }
        .booking-success-sheet__panel { position: relative; z-index: 1; width: 100%; max-width: 420px; background: #fff; border-radius: 20px; padding: 24px; box-shadow: 0 24px 64px rgba(0,0,0,0.18); }
        .booking-success-sheet__title { margin: 0 0 8px; font-size: 1.1rem; font-weight: 800; color: #1e293b; }
        .booking-success-sheet__when { margin: 0 0 4px; font-size: 0.875rem; color: #64748b; }
        .booking-success-sheet__event-title { margin: 0 0 12px; font-size: 0.9rem; font-weight: 600; color: #334155; }
        .booking-success-sheet__details { margin: 0 0 16px; padding-left: 1.1rem; font-size: 0.85rem; color: #475569; }
        .booking-success-sheet__details li { margin-bottom: 4px; }
        .booking-success-sheet__calendar { margin-bottom: 12px; }
        .booking-success-sheet__done { width: 100%; background: #f1f5f9; border: none; border-radius: 12px; padding: 11px 0; font-weight: 600; font-size: 0.875rem; color: #475569; cursor: pointer; }
      `}</style>
    </div>,
    document.body,
  )
}
