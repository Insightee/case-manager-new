import { apiFetch, apiUpload } from './apiClient.js'

export function appendTicketFiles(formData, files, fieldName = 'files') {
  for (const f of files) {
    formData.append(fieldName, f)
  }
}

export async function createStaffTicket({ subject, body, category, topic, case_id, files = [] }) {
  const payload = {
    subject,
    body,
    category: category || 'OTHER',
    ...(topic ? { topic } : {}),
    ...(case_id != null && case_id !== '' ? { case_id: Number(case_id) } : {}),
  }
  if (files.length > 0) {
    const fd = new FormData()
    fd.append('subject', subject)
    fd.append('body', body)
    fd.append('category', category || 'OTHER')
    if (topic) fd.append('topic', topic)
    if (case_id != null && case_id !== '') fd.append('case_id', String(case_id))
    appendTicketFiles(fd, files)
    return apiUpload('/api/v1/tickets', fd)
  }
  return apiFetch('/api/v1/tickets', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function replyStaffTicket(ticketId, body, files = [], { isInternal = false } = {}) {
  if (files.length > 0) {
    const fd = new FormData()
    fd.append('body', body)
    if (isInternal) fd.append('is_internal', 'true')
    appendTicketFiles(fd, files)
    return apiUpload(`/api/v1/tickets/${ticketId}/messages`, fd)
  }
  return apiFetch(`/api/v1/tickets/${ticketId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ body, is_internal: isInternal }),
  })
}

export async function createParentTicket({ subject, message, topic, case_id, files = [] }) {
  if (files.length > 0) {
    const fd = new FormData()
    fd.append('subject', subject)
    fd.append('message', message)
    fd.append('topic', topic || 'OTHER')
    if (case_id != null) fd.append('case_id', String(case_id))
    appendTicketFiles(fd, files)
    return apiUpload('/api/v1/parent/support-requests', fd)
  }
  return apiFetch('/api/v1/parent/support-requests', {
    method: 'POST',
    body: JSON.stringify({ subject, message, topic: topic || 'OTHER', case_id }),
  })
}

export async function replyParentTicket(ticketId, body, files = []) {
  if (files.length > 0) {
    const fd = new FormData()
    fd.append('body', body)
    appendTicketFiles(fd, files)
    return apiUpload(`/api/v1/parent/support/tickets/${ticketId}/messages`, fd)
  }
  return apiFetch(`/api/v1/parent/support/tickets/${ticketId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ body }),
  })
}
