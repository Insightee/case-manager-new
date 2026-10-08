#!/usr/bin/env node
/**
 * Insighte release label: iMMDD in Asia/Kolkata, optional .N when RELEASE_SEQ > 1.
 * Shared by Vite build and write-version-json.mjs.
 */

const IST = 'Asia/Kolkata'

/**
 * @param {Date} date
 * @returns {{ month: number, day: number, year: number }}
 */
export function istCalendarPartsFromDate(date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: IST,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const pick = (type) => parts.find((p) => p.type === type)?.value
  return {
    year: Number(pick('year')),
    month: Number(pick('month')),
    day: Number(pick('day')),
  }
}

/**
 * @param {{ month: number, day: number, releaseSeq?: number }} input
 */
export function formatReleaseLabel({ month, day, releaseSeq = 1 }) {
  const mm = String(month).padStart(2, '0')
  const dd = String(day).padStart(2, '0')
  const seq = Number(releaseSeq) || 1
  if (seq <= 1) return `i${mm}${dd}`
  return `i${mm}${dd}.${seq}`
}

/**
 * @param {Date} [at]
 * @param {number} [releaseSeq]
 */
export function releaseLabelForBuild(at = new Date(), releaseSeq = resolveReleaseSeq()) {
  const { month, day } = istCalendarPartsFromDate(at)
  return formatReleaseLabel({ month, day, releaseSeq })
}

export function resolveReleaseSeq() {
  const raw = process.env.RELEASE_SEQ ?? process.env.VITE_RELEASE_SEQ ?? '1'
  const n = Number.parseInt(String(raw), 10)
  return Number.isFinite(n) && n >= 1 ? n : 1
}

/**
 * @param {{ buildId: string, builtAt?: string, releaseSeq?: number }} opts
 */
export function buildVersionManifest(opts) {
  const builtAt = opts.builtAt || new Date().toISOString()
  const at = new Date(builtAt)
  const releaseSeq = opts.releaseSeq ?? resolveReleaseSeq()
  const releaseLabel = releaseLabelForBuild(at, releaseSeq)
  return {
    buildId: opts.buildId,
    releaseLabel,
    releaseSeq,
    builtAt,
    timezone: IST,
  }
}
