import { TherapistCalendar } from './TherapistCalendar.jsx'

/**
 * Parent booking calendar — thin wrapper around TherapistCalendar.
 */
export function ClientCalendar({
  caseId,
  therapistId,
  onSlotClick,
  selectedSlotId,
  refreshKey = 0,
  onCalendarLoad,
}) {
  if (!caseId || !therapistId) {
    return <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>Select a case and therapist to view the calendar.</p>
  }

  return (
    <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
      <div style={{ minWidth: 480 }}>
        <TherapistCalendar
          therapistId={therapistId}
          caseId={caseId}
          apiPrefix="/api/v1/parent/booking"
          mode="parent"
          onSlotClick={onSlotClick}
          selectedSlotId={selectedSlotId}
          refreshKey={refreshKey}
          showLeaveActions={false}
          onCalendarLoad={onCalendarLoad}
        />
      </div>
    </div>
  )
}
