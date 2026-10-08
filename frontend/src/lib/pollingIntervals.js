/**
 * Client polling / refresh intervals in one place (same for parent, therapist and admin portals).
 * The app is designed to keep request volume low; change these rather than adding new timers.
 * Unchanged on purpose: report-editor draft autosave (5 min) and login keep-alive (25 min).
 */

const MINUTE = 60 * 1000

/** Notification bell background refresh while the tab is visible (also loads on page load and on open). */
export const NOTIFICATION_POLL_MS = 10 * MINUTE

/** Admin platform-stats page auto-refresh (manual Refresh button is always available). */
export const ADMIN_STATS_REFRESH_MS = 10 * MINUTE

/** react-query: on window focus, refetch only data older than this. */
export const FOCUS_REFETCH_MIN_AGE_MS = 10 * MINUTE

/** Shorter focus threshold for "live" screens: today's schedule, session marking, logs, parent home/appointments. */
export const LIVE_FOCUS_REFETCH_MIN_AGE_MS = 2 * MINUTE

/** Staff directory cache (invalidated by any staff create/edit/deactivate request). */
export const STAFF_DIRECTORY_CACHE_MS = 30 * MINUTE

/** App-usage batch upload; still flushed immediately on tab hide / page close. */
export const USAGE_FLUSH_INTERVAL_MS = 30 * MINUTE
