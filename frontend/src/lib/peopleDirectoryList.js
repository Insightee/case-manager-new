export const PEOPLE_PAGE_SIZE = 15

export const THERAPIST_SORT_OPTIONS = [
  { value: 'id_asc', label: 'Therapist ID (low → high)' },
  { value: 'id_desc', label: 'Therapist ID (high → low)' },
  { value: 'name_asc', label: 'Name (A → Z)' },
  { value: 'name_desc', label: 'Name (Z → A)' },
]

function therapistIdRaw(user) {
  return String(user.external_employee_id || user.staff_id || '').trim()
}

export function hasTherapistId(user) {
  return Boolean(therapistIdRaw(user))
}

function therapistIdNumeric(user) {
  const raw = therapistIdRaw(user)
  if (!raw) return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

function personSortName(user) {
  return (user.full_name || user.email || '').trim().toLowerCase()
}

function compareTherapistIds(a, b, direction) {
  const aMissing = !hasTherapistId(a)
  const bMissing = !hasTherapistId(b)
  if (aMissing && bMissing) return personSortName(a).localeCompare(personSortName(b))
  if (aMissing) return -1
  if (bMissing) return 1
  const aNum = therapistIdNumeric(a) ?? 0
  const bNum = therapistIdNumeric(b) ?? 0
  return direction === 'desc' ? bNum - aNum : aNum - bNum
}

export function sortTherapists(list, sortKey = 'id_asc') {
  const items = [...list]
  switch (sortKey) {
    case 'id_desc':
      return items.sort((a, b) => compareTherapistIds(a, b, 'desc'))
    case 'name_asc':
      return items.sort((a, b) => personSortName(a).localeCompare(personSortName(b)))
    case 'name_desc':
      return items.sort((a, b) => personSortName(b).localeCompare(personSortName(a)))
    case 'id_asc':
    default:
      return items.sort((a, b) => compareTherapistIds(a, b, 'asc'))
  }
}

export function sortStaffAlphabetical(list) {
  return [...list].sort((a, b) => personSortName(a).localeCompare(personSortName(b)))
}

export function sortClientsAlphabetical(list) {
  return [...list].sort((a, b) =>
    (a.childName || '').toLowerCase().localeCompare((b.childName || '').toLowerCase()),
  )
}

export function paginateList(list, page, pageSize = PEOPLE_PAGE_SIZE) {
  const total = list.length
  if (total === 0) {
    return { items: [], page: 1, totalPages: 1, total: 0, rangeStart: 0, rangeEnd: 0 }
  }
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const safePage = Math.min(Math.max(1, page), totalPages)
  const start = (safePage - 1) * pageSize
  const end = Math.min(start + pageSize, total)
  return {
    items: list.slice(start, end),
    page: safePage,
    totalPages,
    total,
    rangeStart: start + 1,
    rangeEnd: end,
  }
}

/** @returns {(number|string)[]} */
export function buildPageNumbers(current, totalPages) {
  if (totalPages <= 0) return []
  if (totalPages === 1) return [1]
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1)
  }
  const pages = new Set([1, totalPages, current, current - 1, current + 1])
  const sorted = [...pages].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b)
  const result = []
  let prev = 0
  for (const p of sorted) {
    if (prev && p - prev > 1) result.push('…')
    result.push(p)
    prev = p
  }
  return result
}
