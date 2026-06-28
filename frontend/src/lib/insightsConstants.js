/** Insight types for the Insights Engine — keep in sync with backend enums. */

export const INSIGHT_TYPES = [
  { value: 'full_snapshot', label: 'Full Snapshot' },
  { value: 'goal_suggestions', label: 'Goal Suggestions' },
  { value: 'strategy_review', label: 'Strategy Review' },
  { value: 'supports_accommodations', label: 'Supports' },
  { value: 'what_not_working', label: "What's Not Working" },
  { value: 'parent_safe_draft', label: 'Parent-safe Draft' },
]

export const SNAPSHOT_STATUS_LABELS = {
  draft: 'Draft',
  saved: 'Saved',
  sent_for_review: 'Sent for review',
  approved: 'Approved',
  rejected: 'Rejected',
  archived: 'Archived',
}

export const EVIDENCE_LABELS = {
  insufficient: 'Insufficient evidence',
  weak: 'Weak evidence',
  moderate: 'Moderate evidence',
  strong_operational: 'Stronger evidence',
}

export function monthOptions(count = 12) {
  const opts = []
  const now = new Date()
  for (let i = 0; i < count; i += 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
    opts.push({ value, label })
  }
  return opts
}

export function currentMonthValue() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}
