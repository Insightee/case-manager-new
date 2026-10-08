/** Client release label (iMMDD IST) — mirrors frontend/scripts/releaseLabel.mjs */

export const RELEASE_LABEL_TIMEZONE = 'Asia/Kolkata'

const LABEL_RE = /^i(\d{2})(\d{2})(?:\.(\d+))?$/

/**
 * @param {Date} date
 * @returns {{ month: number, day: number, year: number }}
 */
export function istCalendarPartsFromDate(date) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: RELEASE_LABEL_TIMEZONE,
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
 * @param {string} label
 * @returns {{ mmdd: number, seq: number } | null}
 */
export function parseReleaseLabel(label) {
  const raw = String(label || '').trim()
  const m = LABEL_RE.exec(raw)
  if (!m) return null
  const month = Number(m[1])
  const day = Number(m[2])
  const mmdd = month * 100 + day
  const seq = m[3] ? Number(m[3]) : 1
  if (!Number.isFinite(mmdd) || !Number.isFinite(seq) || seq < 1) return null
  return { mmdd, seq }
}

/**
 * @returns {-1 | 0 | 1} negative if a is older than b
 */
export function compareReleaseLabels(a, b) {
  const pa = parseReleaseLabel(a)
  const pb = parseReleaseLabel(b)
  if (!pa || !pb) return 0
  if (pa.mmdd !== pb.mmdd) return pa.mmdd < pb.mmdd ? -1 : 1
  if (pa.seq !== pb.seq) return pa.seq < pb.seq ? -1 : 1
  return 0
}

/**
 * True when deployed label is a newer release than the embedded client label.
 * @param {string} embedded
 * @param {string | null | undefined} remote
 */
export function isDeployedReleaseNewer(embedded, remote) {
  if (!embedded || !remote) return false
  if (embedded === 'dev' || remote === 'dev') return false
  const cmp = compareReleaseLabels(embedded, remote)
  if (cmp === 0) return false
  return cmp < 0
}

/** @returns {string} */
export function getEmbeddedReleaseLabel() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_RELEASE_LABEL) {
    return String(import.meta.env.VITE_RELEASE_LABEL)
  }
  return 'dev'
}
