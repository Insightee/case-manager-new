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
 * @param {Record<string, unknown> | null | undefined} migrationInfo
 */
export function migrationBannerMessage(migrationInfo) {
  if (!migrationInfo?.window_active) return null
  return migrationInfo.banner_message || null
}
