import { migrationBannerMessage } from '../../lib/leaveMigration.js'
import '../therapist/therapist-leave.css'

/** Temporary July backfill banner — therapist leave + child absence. */
export function MigrationBackfillBanner({ migrationInfo, style }) {
  const message = migrationBannerMessage(migrationInfo)
  if (!message) return null
  return (
    <div
      className="therapist-leave-page__migration-banner"
      role="status"
      style={style}
    >
      {message}
    </div>
  )
}
