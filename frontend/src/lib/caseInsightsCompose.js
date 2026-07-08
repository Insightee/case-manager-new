/**
 * Case Insights tab — light client-side composition on top of the already-normalized
 * `GET /cases/{id}/insights/case-summary` payload (backend does the heavy lifting; see
 * `docs/design/stitch/insights-tab/DESIGN.md`). No AI, no extra fetches — pure functions only.
 */

import { formatTimestampDateIN } from './datetime.js'

const STATUS_TONE_MAP = {
  Consistent: 'positive',
  Helpful: 'positive',
  'Approved strategy': 'positive',
  'Pool candidate': 'positive',
  Building: 'progress',
  'Partly helpful': 'progress',
  Emerging: 'muted',
  'Not enough evidence': 'muted',
  'Case-specific': 'muted',
  'Pending CM review': 'muted',
  'Suggested adaptation': 'muted',
  'Needs adapting': 'attention',
  incorporated: 'positive',
  not_incorporated: 'muted',
}

export function statusTone(status) {
  return STATUS_TONE_MAP[status] || 'muted'
}

export function formatInsightDate(iso) {
  if (!iso) return null
  return formatTimestampDateIN(iso) || null
}

/** Goals ordered so the weakest-evidence goal (most in need of attention) surfaces first. */
export function sortGoalsByAttentionNeeded(goals = []) {
  const priority = {
    'Not enough evidence': 0,
    'Needs adapting': 1,
    Emerging: 2,
    Building: 3,
    Consistent: 4,
  }
  return [...goals].sort((a, b) => (priority[a.status] ?? 2) - (priority[b.status] ?? 2))
}
