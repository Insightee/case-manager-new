/** Filter + display helpers for the case Reports tab. */

const TYPE_LABELS = {
  observation_report: 'Observation Report',
  monthly_report: 'Monthly Report',
  iep: 'IEP',
  progress_report: 'Progress Report',
  cm_meeting_note: 'CM Meeting Note',
}

export function reportTypeLabel(type) {
  return TYPE_LABELS[type] || type || 'Report'
}

export function statusTone(status, statusLabel) {
  const s = String(status || statusLabel || '').toLowerCase()
  if (s.includes('overdue') || s.includes('needs change') || s.includes('rejected')) return 'attention'
  if (s.includes('approved') || s.includes('completed') || s.includes('active') || s.includes('published')) {
    return 'positive'
  }
  if (s.includes('draft') || s.includes('pending') || s.includes('due soon') || s.includes('review')) {
    return 'progress'
  }
  return 'muted'
}

export function attentionAccent(priority) {
  if (priority === 'overdue' || priority === 'needs_changes') return 'error'
  if (priority === 'due_soon' || priority === 'not_started') return 'warning'
  if (priority === 'pending_cm_approval') return 'neutral'
  return 'secondary'
}

const DEFAULT_FILTERS = {
  search: '',
  month: 'all',
  year: 'all',
  type: 'all',
  status: 'all',
}

export function filterHistory(historyGroups, filters = DEFAULT_FILTERS) {
  const q = (filters.search || '').trim().toLowerCase()
  return historyGroups
    .filter((group) => {
      if (filters.year !== 'all' && !group.month.startsWith(String(filters.year))) return false
      if (filters.month !== 'all' && group.month !== filters.month) return false
      return true
    })
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => {
        if (filters.type !== 'all' && item.type !== filters.type) return false
        if (filters.status !== 'all') {
          const st = String(item.status || '').toLowerCase()
          const label = String(item.status_label || '').toLowerCase()
          const want = filters.status.toLowerCase()
          if (want === 'needs_changes' && !st.includes('return') && !st.includes('reject') && !label.includes('change')) {
            return false
          }
          if (want === 'pending_cm_approval' && !st.includes('submitted') && !st.includes('review') && !label.includes('pending')) {
            return false
          }
          if (want === 'draft' && !st.includes('draft') && !label.includes('draft')) return false
          if (want === 'approved' && !st.includes('approved') && !label.includes('approved') && !label.includes('completed')) {
            return false
          }
          if (want === 'overdue' && !st.includes('overdue') && !label.includes('overdue')) return false
          if (want === 'due_soon' && !st.includes('due') && !label.includes('due soon')) return false
          if (
            !['needs_changes', 'pending_cm_approval', 'draft', 'approved', 'overdue', 'due_soon'].includes(want) &&
            st !== want &&
            !label.includes(want.replace(/_/g, ' '))
          ) {
            return false
          }
        }
        if (!q) return true
        const hay = [item.title, item.summary, item.status_label, item.type, group.label]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        return hay.includes(q)
      }),
    }))
    .filter((g) => g.items.length > 0)
}

export function monthOptionsFromHistory(historyGroups) {
  return historyGroups.map((g) => ({ value: g.month, label: g.label }))
}

export function yearOptionsFromFilters(filtersMeta) {
  return (filtersMeta?.available_years || []).map((y) => ({ value: String(y), label: String(y) }))
}

export function navigateToReport(navigate, targetUrl) {
  if (!targetUrl) return
  if (targetUrl.startsWith('http')) {
    window.location.href = targetUrl
    return
  }
  const [path, search] = targetUrl.split('?')
  if (search) {
    const params = new URLSearchParams(search)
    navigate({ pathname: path, search: `?${params.toString()}` })
  } else {
    navigate(path)
  }
}
