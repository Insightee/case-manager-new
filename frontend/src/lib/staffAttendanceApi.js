import { apiDownload, apiFetch } from './apiClient.js'

export function fetchTodayAttendance() {
  return apiFetch('/api/v1/staff-attendance/me/today')
}

export function clockInStaff(payload) {
  return apiFetch('/api/v1/staff-attendance/clock-in', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function pauseStaffAttendance() {
  return apiFetch('/api/v1/staff-attendance/pause', { method: 'POST' })
}

export function resumeStaffAttendance() {
  return apiFetch('/api/v1/staff-attendance/resume', { method: 'POST' })
}

export function saveStaffWorkSummary(workSummary) {
  return apiFetch('/api/v1/staff-attendance/work-summary', {
    method: 'PUT',
    body: JSON.stringify({ work_summary: workSummary }),
  })
}

export function clockOutStaff(workSummary) {
  return apiFetch('/api/v1/staff-attendance/clock-out', {
    method: 'POST',
    body: JSON.stringify({ work_summary: workSummary || undefined }),
  })
}

export function submitForgotStaffLog(payload) {
  return apiFetch('/api/v1/staff-attendance/forgot', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchMyStaffAttendance({ filter = 'all', search = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ filter, limit: String(limit), offset: String(offset) })
  if (search?.trim()) params.set('search', search.trim())
  return apiFetch(`/api/v1/staff-attendance/me?${params}`)
}

export function fetchUserStaffAttendance(userId, { filter = 'all', search = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ filter, limit: String(limit), offset: String(offset) })
  if (search?.trim()) params.set('search', search.trim())
  return apiFetch(`/api/v1/staff-attendance/users/${userId}?${params}`)
}

export function exportUserStaffAttendanceCsv(userId, { filter = 'all', search = '' } = {}) {
  const params = new URLSearchParams({ filter })
  if (search?.trim()) params.set('search', search.trim())
  return apiDownload(
    `/api/v1/staff-attendance/users/${userId}/export?${params}`,
    `staff-attendance-${userId}.csv`,
  )
}

export function hrUpdateStaffAttendance(attendanceId, payload) {
  return apiFetch(`/api/v1/staff-attendance/records/${attendanceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function createStaffLeave(payload) {
  return apiFetch('/api/v1/staff-attendance/leaves', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchMyStaffLeaves() {
  return apiFetch('/api/v1/staff-attendance/leaves/me')
}

export function fetchStaffLeaveBalance() {
  return apiFetch('/api/v1/staff-attendance/me/leave-balance')
}

export function fetchStaffLeavesAdmin({ status = 'PENDING', search = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ status, limit: String(limit), offset: String(offset) })
  if (search?.trim()) params.set('search', search.trim())
  return apiFetch(`/api/v1/staff-attendance/leaves?${params}`)
}

export function reviewStaffLeave(leaveId, payload) {
  return apiFetch(`/api/v1/staff-attendance/leaves/${leaveId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function cancelStaffLeave(leaveId) {
  return apiFetch(`/api/v1/staff-attendance/leaves/${leaveId}`, { method: 'DELETE' })
}

export function formatDurationSeconds(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return '—'
  const totalMins = Math.floor(Number(seconds) / 60)
  const h = Math.floor(totalMins / 60)
  const m = totalMins % 60
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
