import { effectiveDurationMins } from './sessionTimes.js'

export const SHADOW_HALF_DAY_REFERENCE_MINS = 300
export const SHADOW_FULL_DAY_REFERENCE_MINS = 600
export const HOMECARE_MIN_MINS = 60
export const HOMECARE_MAX_MINS = 240
export const SCHEDULED_DURATION_TOLERANCE_MINS = 15

const EXCLUDED_ATTENDANCE = new Set(['ABSENT', 'CLIENT_ABSENT', 'CLIENT_LEAVE', 'THERAPIST_LEAVE'])

function hasScheduledWindow(session) {
  return Boolean(session?.scheduled_date && session?.start_time && session?.end_time)
}

function scheduledDurationMins(session) {
  if (!hasScheduledWindow(session)) return null
  const [sh, sm] = String(session.start_time).slice(0, 5).split(':').map(Number)
  const [eh, em] = String(session.end_time).slice(0, 5).split(':').map(Number)
  if ([sh, sm, eh, em].some((n) => Number.isNaN(n))) return null
  let startM = sh * 60 + sm
  let endM = eh * 60 + em
  if (endM <= startM) endM += 24 * 60
  return Math.max(1, endM - startM)
}

export function expectedDurationBounds(session) {
  const module = String(session?.product_module || 'homecare').toLowerCase()
  const schedMins = scheduledDurationMins(session)
  if (schedMins != null) {
    return {
      minMins: Math.max(1, schedMins - SCHEDULED_DURATION_TOLERANCE_MINS),
      maxMins: schedMins + SCHEDULED_DURATION_TOLERANCE_MINS,
      referenceLabel: `scheduled ${schedMins} min`,
      hasSchedule: true,
    }
  }
  if (module === 'shadow_support') {
    const dayType = String(session?.day_type || 'FULL_DAY').toUpperCase()
    const ref = dayType === 'HALF_DAY' ? SHADOW_HALF_DAY_REFERENCE_MINS : SHADOW_FULL_DAY_REFERENCE_MINS
    return {
      minMins: ref,
      maxMins: ref,
      referenceLabel: dayType === 'HALF_DAY' ? 'half-day shadow (5 hours)' : 'full-day shadow (10 hours)',
      hasSchedule: false,
    }
  }
  if (module === 'homecare') {
    return {
      minMins: HOMECARE_MIN_MINS,
      maxMins: HOMECARE_MAX_MINS,
      referenceLabel: 'homecare (1–4 hours)',
      hasSchedule: false,
    }
  }
  return {
    minMins: 1,
    maxMins: 600,
    referenceLabel: 'session duration',
    hasSchedule: false,
  }
}

export function isBillableSessionLog(session, log, attendanceStatus) {
  if (!session || session.status !== 'COMPLETED') return false
  const attendance = String(attendanceStatus || log?.attendance_status || 'PRESENT').toUpperCase()
  if (EXCLUDED_ATTENDANCE.has(attendance)) return false
  const excludedStatuses = new Set(['CANCELLED', 'NO_SHOW', 'RESCHEDULED', 'CLIENT_ABSENT', 'THERAPIST_LEAVE'])
  if (excludedStatuses.has(String(session.status || '').toUpperCase())) return false
  return true
}

export function getDurationComplianceWarning({ session, log, attendanceStatus } = {}) {
  if (!isBillableSessionLog(session, log, attendanceStatus)) return null
  const actualMins = effectiveDurationMins(session, log)
  if (actualMins == null) return null
  const bounds = expectedDurationBounds(session)
  if (actualMins >= bounds.minMins && actualMins <= bounds.maxMins) return null

  const under = actualMins < bounds.minMins
  const message = bounds.hasSchedule
    ? `${actualMins} min vs ${bounds.referenceLabel} (±${SCHEDULED_DURATION_TOLERANCE_MINS}).`
    : `${actualMins} min — ${under ? 'below' : 'above'} ${bounds.referenceLabel}.`

  return {
    code: under ? 'under_minimum' : 'over_maximum',
    message,
    actualMins,
    minMins: bounds.minMins,
    maxMins: bounds.maxMins,
    referenceLabel: bounds.referenceLabel,
    hasSchedule: bounds.hasSchedule,
  }
}
