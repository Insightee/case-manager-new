import { apiFetch } from './apiClient.js'
import { todayIsoIST } from './datetime.js'

export function mapParentCases(cases) {
  return (cases || []).map((c) => ({
    id: c.id,
    caseId: c.caseId,
    childName: c.childName,
    serviceType: c.serviceType,
    productModule: c.productModule,
    isHomecare: c.isHomecare,
    serviceAddress: c.serviceAddress,
    serviceAddressSummary: c.serviceAddressSummary,
    therapist: c.therapistName || '—',
    caseManager: c.caseManagerName || '—',
    status: c.status,
    latestApprovedReportMonth: c.latestApprovedReportMonth || '—',
    iepAcknowledgementStatus:
      c.iepStatus === 'acknowledged' ? 'acknowledged' : c.iepStatus === 'pending' ? 'pending' : 'none',
    upcomingBooking: c.upcomingBooking,
  }))
}

export async function fetchParentCases() {
  const cases = await apiFetch('/api/v1/parent/cases')
  return mapParentCases(cases)
}

export function mapParentAppointments(slots, meetings) {
  const slotItems = (slots || []).map((a) => ({
    id: `slot-${a.id}`,
    rawId: a.id,
    isCmMeeting: false,
    caseId: a.caseId,
    caseDbId: a.caseDbId,
    childName: a.childName,
    therapistName: a.therapistName,
    therapistUserId: a.therapistUserId,
    slotDate: a.slotDate,
    startTime: a.startTime,
    endTime: a.endTime,
    approvalStatus: a.approval_status || a.approvalStatus || 'CONFIRMED',
    canCancel: a.can_cancel,
    canReschedule: a.can_reschedule,
    rescheduleReason: a.reschedule_reason,
    cancelReason: a.cancel_reason,
  }))
  const meetingItems = (meetings || []).map((m) => ({
    id: `cm-${m.id}`,
    rawId: m.id,
    isCmMeeting: true,
    caseId: m.case_code,
    caseDbId: m.case_id,
    caseMgrName: m.case_manager_name,
    childName: m.child_name,
    therapistName: null,
    slotDate: m.scheduled_date,
    startTime: m.scheduled_time,
    endTime: null,
    meetingStatus: m.status,
    meetingTitle: m.title,
    approvalStatus: 'CONFIRMED',
    canCancel: false,
    canReschedule: false,
  }))
  return sortAppointmentsByStart([...slotItems, ...meetingItems])
}

export function sortAppointmentsByStart(appointments) {
  return [...(appointments || [])].sort((a, b) => {
    const da = `${a.slotDate || ''}T${a.startTime || '00:00'}`
    const db = `${b.slotDate || ''}T${b.startTime || '00:00'}`
    return da < db ? -1 : da > db ? 1 : 0
  })
}

/** Therapy slots + CM meetings from today onward (excludes completed/cancelled meetings). */
export function filterUpcomingAppointments(appointments, todayIso = todayIsoIST()) {
  return (appointments || []).filter((a) => {
    if (!a?.slotDate || a.slotDate < todayIso) return false
    if (a.isCmMeeting) {
      const st = String(a.meetingStatus || 'SCHEDULED').toUpperCase()
      return st === 'SCHEDULED'
    }
    return true
  })
}

export function upcomingAppointmentsForDashboard(appointments, limit = 2) {
  return sortAppointmentsByStart(filterUpcomingAppointments(appointments)).slice(0, limit)
}

export async function fetchParentAppointments() {
  const [slots, meetings] = await Promise.all([
    apiFetch('/api/v1/parent/appointments').catch(() => []),
    apiFetch('/api/v1/parent/cm-meetings?status=SCHEDULED').catch(() => []),
  ])
  return mapParentAppointments(slots, meetings)
}
