/** @typedef {import('./apiClient.js').ApiFetch} ApiFetch */

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
  if (!migrationInfo?.window_active) return null
  return migrationInfo.banner_message || null
}

/**
 * @param {Record<string, unknown> | null | undefined} migrationInfo
 */
export function migrationBackfillDateBounds(migrationInfo) {
  if (!migrationInfo?.window_active) return null
  return {
    min: migrationInfo.reentry_start,
    max: migrationInfo.reentry_end,
  }
}
