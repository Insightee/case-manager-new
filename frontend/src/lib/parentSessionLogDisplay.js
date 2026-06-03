/**
 * Parent-facing session log layout — mirrors therapist SubmitSessionLogForm fields.
 */

export const PARENT_LOG_SECTIONS = [
  {
    key: 'parent_notes',
    label: 'Update for family',
    hint: 'From your therapist',
    variant: 'highlight',
  },
  {
    key: 'activities_done',
    fallbackKey: 'what_we_did',
    label: 'What we did today',
    hint: null,
    variant: 'default',
  },
  {
    key: 'goals_addressed',
    label: 'Goals worked on',
    hint: null,
    variant: 'default',
  },
  {
    key: 'follow_ups',
    fallbackKey: 'what_is_next',
    label: "What's next",
    hint: null,
    variant: 'default',
  },
]

function norm(text) {
  return (text || '').trim()
}

function sameText(a, b) {
  const x = norm(a)
  const y = norm(b)
  if (!x || !y) return false
  return x === y || x.includes(y) || y.includes(x)
}

/** Structured sections shown to parents (no duplicate headline/summary). */
export function getParentLogSections(log) {
  if (!log) return []
  const familyUpdate = norm(log.parent_notes)
  const sections = []

  for (const def of PARENT_LOG_SECTIONS) {
    const value = norm(log[def.key] || log[def.fallbackKey])
    if (!value) continue
    if (def.key === 'activities_done' && familyUpdate && sameText(familyUpdate, value)) continue
    if (def.key === 'follow_ups' && familyUpdate && sameText(familyUpdate, value)) continue
    sections.push({ ...def, value })
  }
  return sections
}

/** Combined plain text for expand/collapse preview length checks. */
export function getParentLogFullText(log) {
  return getParentLogSections(log)
    .map((s) => s.value)
    .join('\n\n')
}

/** Dashboard/list preview when only a teaser is needed. */
export function getParentLogPreview(log) {
  const sections = getParentLogSections(log)
  const highlight = sections.find((s) => s.variant === 'highlight')
  if (highlight) return highlight.value
  return sections[0]?.value || null
}

function formatClockPart(raw) {
  if (!raw) return ''
  const s = String(raw)
  const match = s.match(/^(\d{1,2}):(\d{2})/)
  if (match) {
    const h = parseInt(match[1], 10)
    const m = match[2]
    const period = h >= 12 ? 'PM' : 'AM'
    const h12 = h % 12 || 12
    return `${h12}:${m} ${period}`
  }
  return s.slice(0, 5)
}

export function formatParentLogSessionTime(log) {
  if (log?.actual_start_at && log?.actual_end_at) {
    try {
      const start = new Date(log.actual_start_at).toLocaleTimeString(undefined, {
        hour: 'numeric',
        minute: '2-digit',
      })
      const end = new Date(log.actual_end_at).toLocaleTimeString(undefined, {
        hour: 'numeric',
        minute: '2-digit',
      })
      return `${start} – ${end}`
    } catch {
      /* fall through */
    }
  }
  if (log?.start_time && log?.end_time) {
    return `${formatClockPart(log.start_time)} – ${formatClockPart(log.end_time)}`
  }
  if (log?.start_time) return formatClockPart(log.start_time)
  return ''
}
