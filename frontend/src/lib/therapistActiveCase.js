const ACTIVE_KEY = 'ic-therapist-active-case'
const RECENT_KEY = 'ic-therapist-recent-cases'
const MAX_RECENT = 6

export function loadActiveCase() {
  try {
    const raw = sessionStorage.getItem(ACTIVE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.id) return null
    return parsed
  } catch {
    return null
  }
}

export function saveActiveCase(row) {
  try {
    if (!row?.id) {
      sessionStorage.removeItem(ACTIVE_KEY)
      return
    }
    sessionStorage.setItem(
      ACTIVE_KEY,
      JSON.stringify({
        id: row.id,
        caseId: row.caseId || row.case_code || row.caseCode,
        child: row.child || row.child_name || row.childName,
      }),
    )
  } catch {
    /* ignore */
  }
}

export function loadRecentCaseIds() {
  try {
    const raw = sessionStorage.getItem(RECENT_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((id) => Number.isFinite(Number(id))) : []
  } catch {
    return []
  }
}

export function pushRecentCaseId(caseId) {
  const id = Number(caseId)
  if (!Number.isFinite(id)) return
  const prev = loadRecentCaseIds().filter((x) => x !== id)
  const next = [id, ...prev].slice(0, MAX_RECENT)
  try {
    sessionStorage.setItem(RECENT_KEY, JSON.stringify(next))
  } catch {
    /* ignore */
  }
}
