/**
 * Parent-facing session log layout — prefers structured session parent summary when present.
 */

import { structuredReadSections } from './sessionLogReadProjection.js'

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
  const structured = structuredReadSections(log)
  if (structured?.parentSummary) {
    const sections = [
      {
        key: 'parent_notes',
        label: 'Update for family',
        hint: 'From your therapist',
        variant: 'highlight',
        value: structured.parentSummary,
      },
    ]
    if (structured.story && structured.story !== structured.parentSummary) {
      sections.push({
        key: 'activities_done',
        label: 'What we did today',
        hint: null,
        variant: 'default',
        value: structured.story,
      })
    }
    return sections
  }
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

function formatIsoTimeRange(startIso, endIso) {
  const start = new Date(startIso).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
  const end = new Date(endIso).toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
  return `${start} – ${end}`
}

/** Approved logs use effective times from API; show (corrected) when therapist edited clock. */
export function formatParentLogSessionTime(log) {
  if (log?.actual_start_at && log?.actual_end_at) {
    try {
      const range = formatIsoTimeRange(log.actual_start_at, log.actual_end_at)
      if (log?.actual_times_edited) {
        return `${range} (corrected)`
      }
      return range
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

/** Optional muted clock record when a correction was approved. */
export function formatParentLogClockFootnote(log) {
  if (!log?.actual_times_edited || !log?.clock_start_at || !log?.clock_end_at) return null
  try {
    return `Originally clocked: ${formatIsoTimeRange(log.clock_start_at, log.clock_end_at)}`
  } catch {
    return null
  }
}
