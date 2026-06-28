import { execSync } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'

const backendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../backend')

/** Ensure org goal bank + strategy pool exist before Clinical Brain E2E (idempotent). */
export default async function globalSetup() {
  execSync(
    `cd "${backendRoot}" && python3 -c "` +
      'from app.core.database import SessionLocal, ensure_sqlite_schema_patches; ' +
      'ensure_sqlite_schema_patches(); ' +
      'from app.seed.demo_clinical_reports_seed import ensure_org_clinical_brain_library, ensure_clinical_brain_phase_seed; ' +
      'db = SessionLocal(); ' +
      'ensure_org_clinical_brain_library(db); ' +
      'ensure_clinical_brain_phase_seed(db); ' +
      'db.close()"',
    { stdio: 'inherit', env: process.env },
  )
}
