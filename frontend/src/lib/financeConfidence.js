/**
 * Stage 1 Finance Control Tower confidence helpers.
 * Frontend may downgrade; never upgrade. Never invent RECONCILED.
 */

export const CONFIDENCE_LEVELS = Object.freeze({
  RECONCILED: 'RECONCILED',
  PARTIAL: 'PARTIAL',
  ESTIMATED: 'ESTIMATED',
  INCOMPLETE: 'INCOMPLETE',
})

const RANK = {
  RECONCILED: 0,
  PARTIAL: 1,
  ESTIMATED: 2,
  INCOMPLETE: 3,
}

const TOOLTIPS = {
  RECONCILED: 'Matches the applicable source-of-truth financial record.',
  PARTIAL: 'Based on persisted calculated rows that are not yet production-reconciled.',
  ESTIMATED: 'Derived from incomplete bases — treat as provisional.',
  INCOMPLETE: 'A material source is missing, so the figure cannot be treated as complete.',
}

export function confidenceTooltip(level) {
  return TOOLTIPS[level] || TOOLTIPS.ESTIMATED
}

export function normalizeConfidence(level, { materialSourceMissing = false } = {}) {
  if (!level || RANK[level] === undefined) {
    return materialSourceMissing ? CONFIDENCE_LEVELS.INCOMPLETE : CONFIDENCE_LEVELS.ESTIMATED
  }
  return level
}

/** Never upgrade. Returns the lower-confidence of current and candidate. */
export function downgradeConfidence(current, candidate) {
  const a = normalizeConfidence(current)
  const b = normalizeConfidence(candidate)
  return RANK[a] >= RANK[b] ? a : b
}

export function lowestConfidence(levels) {
  const list = (levels || []).map((l) => normalizeConfidence(l)).filter(Boolean)
  if (!list.length) return CONFIDENCE_LEVELS.ESTIMATED
  return list.reduce((acc, l) => (RANK[l] > RANK[acc] ? l : acc), CONFIDENCE_LEVELS.RECONCILED)
}

/**
 * Aggregate MoneyValues. If any amount missing/incompatible → do not invent a total.
 * Labels aggregate with lowest confidence among constituents.
 */
export function aggregateMoneyValues(items) {
  const list = (items || []).filter(Boolean)
  if (!list.length) {
    return { value: null, confidence: CONFIDENCE_LEVELS.INCOMPLETE, canSum: false }
  }
  const withValues = list.filter((m) => m.value != null && Number.isFinite(Number(m.value)))
  if (withValues.length !== list.length) {
    return {
      value: null,
      confidence: lowestConfidence(list.map((m) => m.confidence)),
      canSum: false,
      recordCount: list.reduce((n, m) => n + (m.recordCount || 0), 0),
    }
  }
  const total = withValues.reduce((s, m) => s + Number(m.value), 0)
  return {
    value: Math.round(total * 100) / 100,
    confidence: lowestConfidence(withValues.map((m) => m.confidence)),
    canSum: true,
    recordCount: withValues.reduce((n, m) => n + (m.recordCount || 0), 0),
  }
}

export function formatInr(value) {
  if (value == null || !Number.isFinite(Number(value))) return null
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(Number(value))
}
