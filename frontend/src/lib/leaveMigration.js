/** @typedef {import('./apiClient.js').ApiFetch} ApiFetch */

import { todayIsoIST } from './datetime.js'

/** Hard-coded July 2026 backfill — matches backend LEAVE_MIGRATION_END_DATE default. */
const JULY_BACKFILL_START = '2026-07-01'
const JULY_BACKFILL_END = '2026-07-31'

/**
 * Whether the temporary month backfill UI should be shown (therapist leave + child absence).
 * Uses API when available; falls back to July 2026 calendar so the picker works even if
 * migration-info is slow or the API still has a stale end date.
 */
export function isBackfillWindowActive(migrationInfo, todayIso = todayIsoIST()) {
  if (migrationInfo?.window_active === true) return true
  if (
    migrationInfo?.reentry_start &&
    migrationInfo?.window_end &&
    todayIso >= migrationInfo.reentry_start &&
    todayIso <= migrationInfo.window_end
  ) {
    return true
  }
  return todayIso >= JULY_BACKFILL_START && todayIso <= JULY_BACKFILL_END
}

/**
 * @param {Record<string, unknown> | null | undefined} migrationInfo
 */
export function migrationBackfillDateBounds(migrationInfo) {
  if (isBackfillWindowActive(migrationInfo)) {
    return {
      min: migrationInfo?.reentry_start || JULY_BACKFILL_START,
      max: migrationInfo?.reentry_end || JULY_BACKFILL_END,
    }
  }
  return null
}

/**
 * @param {Record<string, unknown> | null | undefined} leave
 * @param {Record<string, unknown> | null | undefined} migrationInfo
 */
export function leaveRetroactiveHint(leave, migrationInfo) {
  if (!leave?.is_retroactive) return null
  return (
    migrationInfo?.hr_retroactive_hint ||
    'Previous leave — approving records it for balance tracking only; booked sessions will not be cancelled.'
  )
}

/**
 * @param {Record<string, unknown> | null | undefined} row
 * @param {Record<string, unknown> | null | undefined} migrationInfo
 */
export function absenceRetroactiveHint(row, migrationInfo) {
  if (!row?.is_retroactive) return null
  return (
    migrationInfo?.hr_retroactive_absence_hint ||
    'Previous absence — approving records the child as absent for billing; visit times were not changed.'
  )
}

/**
 * @param {Record<string, unknown> | null | undefined} migrationInfo
 */
export function migrationBannerMessage(migrationInfo) {
  if (!isBackfillWindowActive(migrationInfo)) return null
  return (
    migrationInfo?.banner_message ||
    'July backfill open through 31 July: re-enter therapist leave or child absence for any day in July 2026. HR will review and approve — live sessions will not be changed for past dates.'
  )
}
